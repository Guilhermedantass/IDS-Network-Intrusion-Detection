"""Extracao de features de fluxo no formato do CIC-IDS-2017.

Reproduz a semantica do CICFlowMeter (Java) que gerou o dataset, para que os
modelos recebam as features na mesma escala do treino:

- tempos (duracao, IAT, active/idle) em microssegundos;
- tamanho de pacote = bytes de payload TCP/UDP, somando o preenchimento
  (padding) do Ethernet, que o CICFlowMeter contava como payload: um quadro
  Ethernet tem no minimo 60 bytes, entao um RST (14 + 20 + 20 = 54 bytes)
  aparece no dataset com 6 bytes de "payload";
- cabecalho = cabecalho TCP (data offset) ou UDP (8 bytes), sem o IP;
- desvio padrao amostral (n - 1);
- o primeiro pacote entra duas vezes nas estatisticas gerais de tamanho
  (Packet Length Mean/Std/Variance e Average Packet Size);
- flags marcadas por fluxo (0 ou 1), nao contadas;
- Down/Up Ratio = divisao inteira de pacotes bwd / fwd;
- fluxo termina no primeiro FIN ou 120 s apos o primeiro pacote.

O sentido "forward" e o do primeiro pacote do fluxo.
"""
import math
import socket
from dataclasses import dataclass

import dpkt

FLOW_TIMEOUT = 120_000_000      # us, duracao maxima de um fluxo
ACTIVITY_TIMEOUT = 5_000_000    # us, pausa que separa periodos active/idle
ETH_MIN_PAYLOAD = 46            # bytes; quadros menores recebem padding ate 60 bytes

FIN, SYN, RST, PSH, ACK, URG = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20

ID_COLUMNS = ['Timestamp', 'Src IP', 'Src Port', 'Dst IP', 'Dst Port', 'Protocol']


@dataclass(slots=True)
class Packet:
    ts: int             # microssegundos
    src: str
    dst: str
    sport: int
    dport: int
    proto: int          # 6 = TCP, 17 = UDP
    payload: int        # bytes de payload, incluindo o padding do Ethernet
    header: int         # bytes do cabecalho TCP/UDP
    flags: int = 0      # flags TCP
    padding: int = 0    # bytes de padding do Ethernet incluidos em `payload`


class Stats:
    """Estatisticas incrementais (Welford): nao guarda os valores."""
    __slots__ = ('n', 'total', 'min', 'max', '_mean', '_m2')

    def __init__(self):
        self.n, self.total, self._mean, self._m2 = 0, 0.0, 0.0, 0.0
        self.min, self.max = math.inf, -math.inf

    def add(self, x):
        self.n += 1
        self.total += x
        self.min, self.max = min(self.min, x), max(self.max, x)
        delta = x - self._mean
        self._mean += delta / self.n
        self._m2 += delta * (x - self._mean)

    @property
    def mean(self):
        return self._mean if self.n else 0.0

    @property
    def std(self):
        return math.sqrt(self._m2 / (self.n - 1)) if self.n > 1 else 0.0

    def summary(self):
        if not self.n:
            return 0.0, 0.0, 0.0, 0.0, 0.0
        return self.total, self.mean, self.std, self.max, self.min


def _rate(value, duration_us):
    """Taxa por segundo; inf/NaN com duracao zero, como no CIC-IDS-2017."""
    if duration_us:
        return value / (duration_us / 1e6)
    return math.inf if value else math.nan


class Flow:
    def __init__(self, pkt: Packet):
        self.src, self.dst = pkt.src, pkt.dst
        self.sport, self.dport, self.proto = pkt.sport, pkt.dport, pkt.proto
        self.start = self.last_seen = pkt.ts
        self.fwd_last = self.bwd_last = None
        self.start_active = self.end_active = pkt.ts

        self.all_len, self.fwd_len, self.bwd_len = Stats(), Stats(), Stats()
        self.flow_iat, self.fwd_iat, self.bwd_iat = Stats(), Stats(), Stats()
        self.active, self.idle = Stats(), Stats()

        self.fwd_header = self.bwd_header = 0
        self.min_seg_fwd = math.inf
        self.act_data_fwd = 0
        self.flags = 0
        self.fwd_psh = False
        self.add(pkt, first=True)
        # O CICFlowMeter conta o primeiro pacote duas vezes nas estatisticas
        # gerais de tamanho (Packet Length Mean/Std/Variance, Average Packet Size)
        self.all_len.add(pkt.payload)

    def is_forward(self, pkt):
        return (pkt.src, pkt.sport, pkt.dst, pkt.dport) == (self.src, self.sport, self.dst, self.dport)

    def add(self, pkt: Packet, first=False):
        if not first:
            self._update_active_idle(pkt.ts)
            self.flow_iat.add(pkt.ts - self.last_seen)
        self.last_seen = pkt.ts
        self.all_len.add(pkt.payload)
        self.flags |= pkt.flags

        if first or self.is_forward(pkt):
            if self.fwd_last is not None:
                self.fwd_iat.add(pkt.ts - self.fwd_last)
            self.fwd_last = pkt.ts
            self.fwd_len.add(pkt.payload)
            self.fwd_header += pkt.header
            self.min_seg_fwd = min(self.min_seg_fwd, pkt.header)
            # act_data_pkt_fwd ignora o primeiro pacote e o padding (como no CICFlowMeter)
            self.act_data_fwd += not first and pkt.payload - pkt.padding >= 1
            self.fwd_psh |= bool(pkt.flags & PSH)
        else:
            if self.bwd_last is not None:
                self.bwd_iat.add(pkt.ts - self.bwd_last)
            self.bwd_last = pkt.ts
            self.bwd_len.add(pkt.payload)
            self.bwd_header += pkt.header

    def _update_active_idle(self, ts):
        if ts - self.end_active > ACTIVITY_TIMEOUT:
            if self.end_active - self.start_active > 0:
                self.active.add(self.end_active - self.start_active)
            self.idle.add(ts - self.end_active)
            self.start_active = self.end_active = ts
        else:
            self.end_active = ts

    def features(self):
        duration = self.last_seen - self.start
        n_fwd, n_bwd = self.fwd_len.n, self.bwd_len.n
        flow_iat_total, flow_iat_mean, flow_iat_std, flow_iat_max, flow_iat_min = self.flow_iat.summary()
        fwd_iat_total, fwd_iat_mean, fwd_iat_std, fwd_iat_max, fwd_iat_min = self.fwd_iat.summary()
        bwd_iat_total, bwd_iat_mean, bwd_iat_std, bwd_iat_max, bwd_iat_min = self.bwd_iat.summary()
        _, active_mean, active_std, active_max, active_min = self.active.summary()
        _, idle_mean, idle_std, idle_max, idle_min = self.idle.summary()
        _, fwd_mean, fwd_std, fwd_max, fwd_min = self.fwd_len.summary()
        _, bwd_mean, bwd_std, bwd_max, bwd_min = self.bwd_len.summary()
        all_total, all_mean, all_std, all_max, all_min = self.all_len.summary()
        total_bytes = self.fwd_len.total + self.bwd_len.total

        return {
            'Timestamp': self.start / 1e6,
            'Src IP': self.src, 'Src Port': self.sport,
            'Dst IP': self.dst, 'Dst Port': self.dport,
            'Protocol': self.proto,
            'Flow Duration': duration,
            'Total Fwd Packets': n_fwd,
            'Total Backward Packets': n_bwd,
            'Total Length of Fwd Packets': self.fwd_len.total,
            'Total Length of Bwd Packets': self.bwd_len.total,
            'Fwd Packet Length Max': fwd_max,
            'Fwd Packet Length Min': fwd_min,
            'Fwd Packet Length Mean': fwd_mean,
            'Fwd Packet Length Std': fwd_std,
            'Bwd Packet Length Max': bwd_max,
            'Bwd Packet Length Min': bwd_min,
            'Bwd Packet Length Mean': bwd_mean,
            'Bwd Packet Length Std': bwd_std,
            'Flow Bytes/s': _rate(total_bytes, duration),
            'Flow Packets/s': _rate(n_fwd + n_bwd, duration),
            'Flow IAT Mean': flow_iat_mean,
            'Flow IAT Std': flow_iat_std,
            'Flow IAT Max': flow_iat_max,
            'Flow IAT Min': flow_iat_min,
            'Fwd IAT Total': fwd_iat_total,
            'Fwd IAT Mean': fwd_iat_mean,
            'Fwd IAT Std': fwd_iat_std,
            'Fwd IAT Max': fwd_iat_max,
            'Fwd IAT Min': fwd_iat_min,
            'Bwd IAT Total': bwd_iat_total,
            'Bwd IAT Mean': bwd_iat_mean,
            'Bwd IAT Std': bwd_iat_std,
            'Bwd IAT Max': bwd_iat_max,
            'Bwd IAT Min': bwd_iat_min,
            'Fwd PSH Flags': int(self.fwd_psh),
            'Fwd Header Length': self.fwd_header,
            'Bwd Header Length': self.bwd_header,
            'Fwd Packets/s': _rate(n_fwd, duration),
            'Bwd Packets/s': _rate(n_bwd, duration),
            'Min Packet Length': all_min,
            'Max Packet Length': all_max,
            'Packet Length Mean': all_mean,
            'Packet Length Std': all_std,
            'Packet Length Variance': all_std ** 2,
            'Average Packet Size': all_total / (n_fwd + n_bwd),
            'Avg Bwd Segment Size': bwd_mean,
            'Subflow Bwd Bytes': self.bwd_len.total,
            'FIN Flag Count': int(bool(self.flags & FIN)),
            'RST Flag Count': int(bool(self.flags & RST)),
            'PSH Flag Count': int(bool(self.flags & PSH)),
            'ACK Flag Count': int(bool(self.flags & ACK)),
            'URG Flag Count': int(bool(self.flags & URG)),
            'Down/Up Ratio': n_bwd // n_fwd if n_fwd else 0,
            'act_data_pkt_fwd': self.act_data_fwd,
            'min_seg_size_forward': self.min_seg_fwd,
            'Active Mean': active_mean, 'Active Std': active_std,
            'Active Max': active_max, 'Active Min': active_min,
            'Idle Mean': idle_mean, 'Idle Std': idle_std,
            'Idle Max': idle_max, 'Idle Min': idle_min,
        }


class FlowMeter:
    """Agrupa pacotes em fluxos bidirecionais e devolve os fluxos encerrados."""

    def __init__(self):
        self.flows = {}

    @staticmethod
    def _key(src, sport, dst, dport, proto):
        return (src, sport, dst, dport, proto)

    def process(self, pkt: Packet):
        """Processa um pacote; devolve a lista de fluxos encerrados por ele (features)."""
        fwd = self._key(pkt.src, pkt.sport, pkt.dst, pkt.dport, pkt.proto)
        rev = self._key(pkt.dst, pkt.dport, pkt.src, pkt.sport, pkt.proto)
        key = fwd if fwd in self.flows else rev if rev in self.flows else None

        if key is None:
            self.flows[fwd] = Flow(pkt)
            return []

        flow = self.flows[key]
        if pkt.ts - flow.start > FLOW_TIMEOUT:
            # O fluxo antigo termina e este pacote inicia um novo
            del self.flows[key]
            self.flows[fwd] = Flow(pkt)
            return [flow.features()]

        flow.add(pkt)
        if pkt.flags & FIN:
            del self.flows[key]
            return [flow.features()]
        return []

    def expire(self, now_us, idle_us=None):
        """Encerra fluxos que passaram do timeout (usado na captura ao vivo).

        Com `idle_us`, tambem encerra fluxos sem pacotes ha mais desse tempo. O
        CICFlowMeter nao faz isso (so encerra no FIN ou em 120 s), mas sem isso um
        port scan, cujos fluxos terminam com RST, so geraria alerta 2 minutos depois.
        """
        done = [k for k, f in self.flows.items()
                if now_us - f.start > FLOW_TIMEOUT
                or (idle_us is not None and now_us - f.last_seen > idle_us)]
        return [self.flows.pop(k).features() for k in done]

    def flush(self):
        """Encerra todos os fluxos abertos (fim do arquivo ou da captura)."""
        done = [f.features() for f in self.flows.values()]
        self.flows.clear()
        return done


def parse_ip(ip, ts_us):
    """Converte um pacote IPv4 do dpkt em Packet (None se nao for TCP/UDP)."""
    seg = ip.data
    if isinstance(seg, dpkt.tcp.TCP):
        header, flags = seg.off * 4, seg.flags
    elif isinstance(seg, dpkt.udp.UDP):
        header, flags = 8, 0
    else:
        return None
    # Padding calculado pelo tamanho do IP, e nao lido do quadro: assim o
    # resultado e o mesmo em loopback, Wi-Fi ou pacotes enviados pela propria maquina.
    padding = max(0, ETH_MIN_PAYLOAD - ip.len)
    return Packet(ts=ts_us, src=socket.inet_ntoa(ip.src), dst=socket.inet_ntoa(ip.dst),
                  sport=seg.sport, dport=seg.dport, proto=ip.p,
                  payload=len(seg.data) + padding, header=header, flags=flags, padding=padding)


def _ip_layer(buf, linktype):
    if linktype == dpkt.pcap.DLT_EN10MB:
        frame = dpkt.ethernet.Ethernet(buf)
    elif linktype == dpkt.pcap.DLT_LINUX_SLL:
        frame = dpkt.sll.SLL(buf)
    elif linktype in (dpkt.pcap.DLT_RAW, 101):   # 101 = LINKTYPE_RAW
        return dpkt.ip.IP(buf)
    else:
        raise ValueError(f'Tipo de enlace nao suportado: {linktype}')
    return frame.data if isinstance(frame.data, dpkt.ip.IP) else None


def read_packets(reader):
    """Gera Packets IPv4 TCP/UDP de um leitor pcap/pcapng do dpkt."""
    linktype = reader.datalink()
    for ts, buf in reader:
        try:
            ip = _ip_layer(buf, linktype)
            pkt = parse_ip(ip, int(round(ts * 1e6))) if ip is not None else None
        except (dpkt.dpkt.UnpackError, IndexError):
            continue    # pacote truncado ou malformado
        if pkt is not None:
            yield pkt


def read_pcap(path):
    """Le um arquivo .pcap/.pcapng e gera Packets IPv4 TCP/UDP."""
    with open(path, 'rb') as f:
        try:
            reader = dpkt.pcap.Reader(f)
        except ValueError:
            f.seek(0)
            reader = dpkt.pcapng.Reader(f)
        yield from read_packets(reader)


def read_stream(stream):
    """Le pacotes de um fluxo pcap continuo (ex.: saida do `tcpdump -w -`)."""
    yield from read_packets(dpkt.pcap.Reader(stream))


def flows_from_pcap(path):
    """Gera as features de todos os fluxos de um PCAP, na ordem em que encerram."""
    meter = FlowMeter()
    for pkt in read_pcap(path):
        yield from meter.process(pkt)
    yield from meter.flush()
