"""Deteccao por volume: olha o trafego somado, e nao um fluxo por vez.

Os modelos classificam cada fluxo isolado, entao nao enxergam um flood (milhares
de conexoes curtas que, uma a uma, parecem normais). Aqui os pacotes sao contados
em baldes de 1 s e, a cada checagem, os ultimos `window` segundos sao comparados
com limites simples:

- SYN Flood: uma origem abrindo conexoes (SYN sem ACK) demais com um destino;
- DDoS: um destino recebendo SYNs de muitas origens ao mesmo tempo;
- UDP Flood: uma origem mandando pacotes UDP demais para um destino, quase sem resposta;
- PortScan: uma origem tentando conexao em portas demais de um destino.

So pacotes que iniciam conexao (SYN sem ACK) contam para SYN Flood, DDoS e
PortScan: as respostas de um servidor vao para muitas portas do cliente e
pareceriam um scan. Scan de portas UDP fica de fora pelo mesmo motivo (respostas
de DNS, por exemplo).

A resposta do UDP e reconhecida pelas portas (sai da porta que recebeu o trafego),
e nao so pelos IPs: na interface lo origem e destino sao o mesmo 127.0.0.1.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass

from .flows import ACK, SYN, Packet

UDP = 17


@dataclass
class Limits:
    window: int = 10                # s olhados em cada checagem
    syn_rate: float = 100           # SYN/s de uma origem para um destino
    ddos_sources: int = 20          # origens diferentes mandando SYN para o mesmo destino
    ddos_syn_rate: float = 200      # SYN/s somando todas as origens
    udp_rate: float = 2000          # pacotes UDP/s de uma origem para um destino
    udp_reply_ratio: float = 0.1    # resposta abaixo dessa fracao = trafego de mao unica
    scan_ports: int = 100           # portas diferentes de um destino na janela
    cooldown: int = 30              # s antes de repetir o mesmo alerta


class _Bucket:
    """Contagens de 1 s de trafego."""
    __slots__ = ('syn', 'udp_to', 'udp_from', 'ports')

    def __init__(self):
        self.syn = Counter()                # (src, dst) -> SYNs
        self.udp_to = Counter()             # (src, dst, porta de destino) -> pacotes UDP
        self.udp_from = Counter()           # (src, dst, porta de origem) -> pacotes UDP
        self.ports = defaultdict(set)       # (src, dst) -> portas que receberam SYN


class VolumeDetector:
    def __init__(self, limits=None):
        self.limits = limits or Limits()
        self.buckets = {}       # segundo (epoch) -> _Bucket
        self.last_alert = {}    # (tipo, src, dst) -> segundo do ultimo alerta

    def add(self, pkt: Packet):
        second = pkt.ts // 1_000_000
        bucket = self.buckets.get(second)
        if bucket is None:
            bucket = self.buckets[second] = _Bucket()
        pair = (pkt.src, pkt.dst)
        if pkt.proto == UDP:
            bucket.udp_to[(pkt.src, pkt.dst, pkt.dport)] += 1
            bucket.udp_from[(pkt.src, pkt.dst, pkt.sport)] += 1
        elif pkt.flags & SYN and not pkt.flags & ACK:
            bucket.syn[pair] += 1
            bucket.ports[pair].add(pkt.dport)

    def check(self, now_us):
        """Devolve os alertas da janela que termina em `now_us` (lista de dicts)."""
        lim = self.limits
        now = now_us // 1_000_000
        start = now - lim.window
        for second in [s for s in self.buckets if s <= start]:
            del self.buckets[second]

        syn, udp_to, udp_from, ports = Counter(), Counter(), Counter(), defaultdict(set)
        for bucket in self.buckets.values():
            syn.update(bucket.syn)
            udp_to.update(bucket.udp_to)
            udp_from.update(bucket.udp_from)
            for pair, p in bucket.ports.items():
                ports[pair] |= p

        alerts = []

        def alert(tipo, src, dst, packets, **extra):
            key = (tipo, src, dst)
            if now - self.last_alert.get(key, -lim.cooldown) < lim.cooldown:
                return
            self.last_alert[key] = now
            alerts.append({'ts': now_us / 1e6, 'type': tipo, 'src_ip': src, 'dst_ip': dst,
                           'packets': packets, 'rate': packets / lim.window,
                           'ports': extra.get('ports'), 'sources': extra.get('sources')})

        per_dst = defaultdict(lambda: [0, 0])  # dst -> [SYNs, origens]
        for (src, dst), n in syn.items():
            per_dst[dst][0] += n
            per_dst[dst][1] += 1
            if n / lim.window >= lim.syn_rate:
                alert('SYN Flood', src, dst, n, ports=len(ports[(src, dst)]))
        for dst, (n, sources) in per_dst.items():
            if sources >= lim.ddos_sources and n / lim.window >= lim.ddos_syn_rate:
                alert('DDoS', None, dst, n, sources=sources)
        udp = defaultdict(lambda: [0, 0])  # (src, dst) -> [pacotes, respostas]
        for (src, dst, dport), n in udp_to.items():
            udp[(src, dst)][0] += n
            udp[(src, dst)][1] += udp_from[(dst, src, dport)]
        for (src, dst), (n, replies) in udp.items():
            if n / lim.window >= lim.udp_rate and replies < n * lim.udp_reply_ratio:
                alert('UDP Flood', src, dst, n)
        for (src, dst), p in ports.items():
            if len(p) >= lim.scan_ports:
                alert('PortScan', src, dst, syn[(src, dst)], ports=len(p))
        return alerts
