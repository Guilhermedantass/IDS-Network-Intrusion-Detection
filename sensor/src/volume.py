"""Deteccao por volume: olha o trafego somado, e nao um fluxo por vez.

Os modelos classificam cada fluxo isolado, entao nao enxergam um flood (milhares
de conexoes curtas que, uma a uma, parecem normais). Aqui os pacotes sao contados
em baldes de 1 s e, a cada checagem, os ultimos `window` segundos sao comparados
com limites simples:

- DDoS: um destino recebendo SYNs de muitas origens ao mesmo tempo;
- SYN Flood: uma origem abrindo conexoes (SYN sem ACK) demais com a mesma porta de um destino;
- PortScan: uma origem tentando conexao em portas demais de um destino;
- UDP Flood: uma origem mandando pacotes UDP demais para um destino, quase sem resposta.

So pacotes que iniciam conexao (SYN sem ACK) contam para SYN Flood, DDoS e
PortScan: as respostas de um servidor vao para muitas portas do cliente e
pareceriam um scan. Scan de portas UDP fica de fora pelo mesmo motivo (respostas
de DNS, por exemplo).

A resposta do UDP e reconhecida pelas portas (sai da porta que recebeu o trafego),
e nao so pelos IPs: na interface lo origem e destino sao o mesmo 127.0.0.1.

Enquanto passa do limite, o ataque fica "ativo" e `match` diz a que ataque um
fluxo pertence; assim o detector da um tipo so por fluxo (ver src.detect).
"""
from collections import Counter, defaultdict
from dataclasses import dataclass

from .flows import ACK, SYN, Packet

TCP, UDP = 6, 17

# ordem de prioridade quando um fluxo cai em mais de um ataque ativo
VOLUME_TYPES = ['DDoS', 'SYN Flood', 'PortScan', 'UDP Flood']
PROTOCOL = {'DDoS': TCP, 'PortScan': TCP, 'SYN Flood': TCP, 'UDP Flood': UDP}


@dataclass
class Limits:
    window: int = 10                # s olhados em cada checagem
    syn_rate: float = 100           # SYN/s de uma origem para a mesma porta de um destino
    ddos_sources: int = 20          # origens diferentes mandando SYN para o mesmo destino
    ddos_source_rate: float = 5     # SYN/s minimo para uma origem contar no DDoS
    ddos_syn_rate: float = 200      # SYN/s somando essas origens
    udp_rate: float = 2000          # pacotes UDP/s de uma origem para um destino
    udp_reply_ratio: float = 0.1    # resposta abaixo dessa fracao = trafego de mao unica
    scan_ports: int = 100           # portas diferentes de um destino na janela
    cooldown: int = 30              # s antes de repetir o mesmo alerta


class _Bucket:
    """Contagens de 1 s de trafego."""
    __slots__ = ('syn', 'udp_to', 'udp_from')

    def __init__(self):
        self.syn = Counter()                # (src, dst, porta de destino) -> SYNs
        self.udp_to = Counter()             # (src, dst, porta de destino) -> pacotes UDP
        self.udp_from = Counter()           # (src, dst, porta de origem) -> pacotes UDP


@dataclass
class Attack:
    """Ataque de volume em andamento: vale para fluxos que comecam entre `start` e `end`."""
    type: str
    src: str | None     # None no DDoS (as origens ficam em `sources`)
    dst: str
    start: float        # s (epoch)
    end: float
    sources: frozenset = frozenset()
    ports: frozenset = frozenset()  # SYN Flood: portas atacadas (as outras podem ser um scan)

    def covers(self, src, dport, ts):
        return (self.start <= ts <= self.end
                and (self.src is not None or src in self.sources)
                and (not self.ports or dport in self.ports))


class VolumeDetector:
    def __init__(self, limits=None):
        self.limits = limits or Limits()
        self.buckets = {}       # segundo (epoch) -> _Bucket
        self.last_alert = {}    # (tipo, src, dst) -> segundo do ultimo alerta
        self.active = {}        # (tipo, src, dst) -> Attack

    def add(self, pkt: Packet):
        second = pkt.ts // 1_000_000
        bucket = self.buckets.get(second)
        if bucket is None:
            bucket = self.buckets[second] = _Bucket()
        if pkt.proto == UDP:
            bucket.udp_to[(pkt.src, pkt.dst, pkt.dport)] += 1
            bucket.udp_from[(pkt.src, pkt.dst, pkt.sport)] += 1
        elif pkt.flags & SYN and not pkt.flags & ACK:
            bucket.syn[(pkt.src, pkt.dst, pkt.dport)] += 1

    def check(self, now_us):
        """Devolve os alertas novos da janela que termina em `now_us` (lista de dicts).

        Cada alerta traz `start`: desde quando os fluxos fazem parte do ataque.
        """
        lim = self.limits
        now = now_us // 1_000_000
        start = now - lim.window
        for second in [s for s in self.buckets if s <= start]:
            del self.buckets[second]

        syn, udp_to, udp_from = Counter(), Counter(), Counter()
        for bucket in self.buckets.values():
            syn.update(bucket.syn)
            udp_to.update(bucket.udp_to)
            udp_from.update(bucket.udp_from)

        alerts = []

        def alert(tipo, src, dst, packets, ports=None, sources=(), flooded=(), dst_port=None):
            key = (tipo, src, dst)
            attack = self.active.get(key)
            if attack is None:
                attack = self.active[key] = Attack(tipo, src, dst, start=float(start), end=0.0)
            attack.end = now_us / 1e6 + lim.window
            attack.sources |= frozenset(sources)
            attack.ports |= frozenset(flooded)
            if now - self.last_alert.get(key, -lim.cooldown) < lim.cooldown:
                return
            self.last_alert[key] = now
            alerts.append({'ts': now_us / 1e6, 'start': attack.start, 'type': tipo, 'src_ip': src,
                           'dst_ip': dst, 'dst_port': dst_port, 'protocol': PROTOCOL[tipo],
                           'packets': packets, 'rate': packets / lim.window,
                           'ports': ports, 'sources': len(sources) or None,
                           'source_ips': sorted(sources)})

        pairs = defaultdict(dict)  # (src, dst) -> {porta: SYNs}
        for (src, dst, dport), n in syn.items():
            pairs[(src, dst)][dport] = n

        per_dst = defaultdict(list)  # dst -> [(src, SYNs)] das origens fortes
        for (src, dst), ports in pairs.items():
            n = sum(ports.values())
            if n / lim.window >= lim.ddos_source_rate:
                per_dst[dst].append((src, n))
        for dst, origens in per_dst.items():
            n = sum(c for _, c in origens)
            if len(origens) >= lim.ddos_sources and n / lim.window >= lim.ddos_syn_rate:
                alert('DDoS', None, dst, n, sources=[s for s, _ in origens])

        for (src, dst), ports in pairs.items():
            flooded = [p for p, n in ports.items() if n / lim.window >= lim.syn_rate]
            if flooded:
                n = sum(ports[p] for p in flooded)
                alert('SYN Flood', src, dst, n, ports=len(flooded), flooded=flooded,
                      dst_port=flooded[0] if len(flooded) == 1 else None)
            scanned = len(ports) - len(flooded)
            if scanned >= lim.scan_ports:
                alert('PortScan', src, dst, sum(ports.values()) - sum(ports[p] for p in flooded), ports=scanned)

        udp = defaultdict(lambda: [0, 0, set()])  # (src, dst) -> [pacotes, respostas, portas]
        for (src, dst, dport), n in udp_to.items():
            udp[(src, dst)][0] += n
            udp[(src, dst)][1] += udp_from[(dst, src, dport)]
            udp[(src, dst)][2].add(dport)
        for (src, dst), (n, replies, ports) in udp.items():
            if n / lim.window >= lim.udp_rate and replies < n * lim.udp_reply_ratio:
                alert('UDP Flood', src, dst, n, ports=len(ports),
                      dst_port=next(iter(ports)) if len(ports) == 1 else None)

        # ataque que parou: sai da lista depois que os fluxos dele ja foram classificados
        for key in [k for k, a in self.active.items() if a.end + lim.window < now]:
            del self.active[key]
        return alerts

    def match(self, src, dst, proto, dport, ts):
        """Tipo do ataque de volume ativo a que o fluxo pertence (ou None)."""
        for tipo in VOLUME_TYPES:
            if PROTOCOL[tipo] != proto:
                continue
            attack = self.active.get((tipo, None if tipo == 'DDoS' else src, dst))
            if attack is not None and attack.covers(src, dport, ts):
                return tipo
        return None
