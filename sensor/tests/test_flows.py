import json
import math
import socket
import sqlite3

import dpkt
import pytest

from src import detect
from src.flows import ACK, FIN, PSH, RST, SYN, FlowMeter, Packet, flows_from_pcap
from src.pipeline import MODELS_DIR

CLIENT, SERVER = ('10.0.0.1', 50000), ('10.0.0.2', 80)


def pkt(ts, forward=True, payload=0, header=32, flags=ACK, proto=6):
    (src, sport), (dst, dport) = (CLIENT, SERVER) if forward else (SERVER, CLIENT)
    return Packet(ts=ts, src=src, dst=dst, sport=sport, dport=dport, proto=proto,
                  payload=payload, header=header, flags=flags)


def run_meter(packets):
    meter = FlowMeter()
    flows = [f for p in packets for f in meter.process(p)]
    return flows + meter.flush()


def handshake_flow():
    return [
        pkt(0, payload=0, header=40, flags=SYN),
        pkt(100, forward=False, header=40, flags=SYN | ACK),
        pkt(150),
        pkt(200, payload=100, flags=PSH | ACK),
        pkt(400, forward=False, payload=300, flags=PSH | ACK),
        pkt(1000, flags=FIN | ACK),
    ]


def test_tcp_flow_features():
    [f] = run_meter(handshake_flow())

    assert f['Flow Duration'] == 1000
    assert (f['Total Fwd Packets'], f['Total Backward Packets']) == (4, 2)
    assert f['Total Length of Fwd Packets'] == 100
    assert (f['Fwd Packet Length Max'], f['Fwd Packet Length Min']) == (100, 0)
    assert f['Fwd Packet Length Mean'] == pytest.approx(25)
    assert f['Fwd Packet Length Std'] == pytest.approx(50)        # desvio amostral de [0, 0, 100, 0]
    assert f['Flow IAT Mean'] == pytest.approx(200)               # [100, 50, 50, 200, 600]
    assert f['Flow IAT Min'] == 50
    assert (f['Fwd IAT Min'], f['Fwd IAT Max']) == (50, 800)      # [150, 50, 800]
    assert f['Bwd IAT Total'] == 300
    assert f['Flow Bytes/s'] == pytest.approx(400 / 0.001)
    assert f['Flow Packets/s'] == pytest.approx(6 / 0.001)
    # primeiro pacote (payload 0) contado duas vezes: 7 valores, soma 400
    assert f['Packet Length Mean'] == pytest.approx(400 / 7)
    assert f['Average Packet Size'] == pytest.approx(400 / 6)
    assert f['Packet Length Variance'] == pytest.approx(f['Packet Length Std'] ** 2)
    assert (f['Min Packet Length'], f['Max Packet Length']) == (0, 300)
    assert f['Bwd Header Length'] == 72
    assert f['min_seg_size_forward'] == 32
    assert f['act_data_pkt_fwd'] == 1
    assert f['Down/Up Ratio'] == 0                                # 2 // 4
    assert (f['FIN Flag Count'], f['PSH Flag Count'], f['ACK Flag Count'], f['RST Flag Count']) == (1, 1, 1, 0)
    assert f['Fwd PSH Flags'] == 1


def test_fin_closes_flow_and_next_packet_starts_new_one():
    flows = run_meter(handshake_flow() + [pkt(1100, forward=False)])
    assert len(flows) == 2
    assert flows[1]['Total Fwd Packets'] == 1
    assert flows[1]['Src IP'] == SERVER[0]      # o novo fluxo comeca no sentido do pacote


def test_flow_timeout_120s():
    flows = run_meter([pkt(0), pkt(60_000_000), pkt(121_000_000)])
    assert len(flows) == 2
    assert flows[0]['Flow Duration'] == 60_000_000


def test_single_packet_flow_rates():
    [f] = run_meter([pkt(0, payload=0, flags=SYN)])
    assert f['Flow Duration'] == 0
    assert math.isnan(f['Flow Bytes/s'])        # 0 bytes / 0 s
    assert math.isinf(f['Flow Packets/s'])      # 1 pacote / 0 s


def test_active_idle():
    [f] = run_meter([pkt(0), pkt(1_000_000), pkt(7_000_000), pkt(8_000_000)])
    assert f['Active Mean'] == 1_000_000
    assert f['Idle Mean'] == 6_000_000


def test_extractor_has_all_model_features():
    needed = set()
    for name in ['modelo_binario', 'modelo_tipo_ataque']:
        with open(MODELS_DIR / f'{name}.json', encoding='utf-8') as fh:
            needed |= set(json.load(fh)['features'])
    [f] = run_meter(handshake_flow())
    assert needed <= set(f)


def write_pcap(path, packets):
    """Escreve Packets como um PCAP Ethernet/IPv4/TCP."""
    with open(path, 'wb') as fh:
        writer = dpkt.pcap.Writer(fh)
        for p in packets:
            tcp = dpkt.tcp.TCP(sport=p.sport, dport=p.dport, flags=p.flags, data=b'x' * p.payload)
            tcp.off = p.header // 4
            if p.header > 20:
                tcp.opts = b'\x01' * (p.header - 20)    # NOPs como opcoes TCP
            ip = dpkt.ip.IP(src=socket.inet_aton(p.src), dst=socket.inet_aton(p.dst), p=6, data=tcp)
            eth = dpkt.ethernet.Ethernet(type=dpkt.ethernet.ETH_TYPE_IP, data=ip)
            writer.writepkt(bytes(eth), ts=p.ts / 1e6)


def test_pcap_roundtrip(tmp_path):
    path = tmp_path / 'fluxo.pcap'
    write_pcap(path, handshake_flow())
    [f] = list(flows_from_pcap(path))
    expected = run_meter(handshake_flow())[0]
    for col in ['Flow Duration', 'Total Fwd Packets', 'Total Backward Packets',
                'Total Length of Fwd Packets', 'Bwd Header Length', 'min_seg_size_forward']:
        assert f[col] == expected[col], col


def test_ethernet_padding_counts_as_payload(tmp_path):
    # SYN com cabecalho de 24 bytes (IP 44 bytes) e RST de 20 bytes (IP 40 bytes):
    # no CIC-IDS-2017 eles aparecem com 2 e 6 bytes de payload
    path = tmp_path / 'scan.pcap'
    write_pcap(path, [pkt(0, header=24, flags=SYN), pkt(50, forward=False, header=20, flags=RST | ACK)])
    [f] = list(flows_from_pcap(path))
    assert f['Total Length of Fwd Packets'] == 2
    assert f['Bwd Packet Length Min'] == 6
    assert f['act_data_pkt_fwd'] == 0           # padding nao conta como dado


def test_act_data_ignores_first_packet():
    [f] = run_meter([pkt(0, payload=50), pkt(10, payload=50), pkt(20, forward=False)])
    assert f['act_data_pkt_fwd'] == 1


def test_detect_end_to_end(tmp_path):
    pcap, db = tmp_path / 'fluxo.pcap', tmp_path / 'ids.db'
    # handshake completo + SYN sem resposta para 50 portas (padrao de port scan)
    scan = [Packet(ts=2_000_000 + i * 10, src='10.0.0.9', dst='10.0.0.2', sport=40000, dport=1000 + i,
                   proto=6, payload=0, header=24, flags=SYN) for i in range(50)]
    write_pcap(pcap, handshake_flow() + scan)

    run_id = detect.run(pcap, db, batch_size=10)

    conn = sqlite3.connect(db)
    flows, attacks = conn.execute('SELECT flows, attacks FROM runs WHERE id = ?', (run_id,)).fetchone()
    assert flows == 51
    saved = conn.execute('SELECT COUNT(*) FROM flows WHERE is_attack = 1 AND features IS NOT NULL').fetchone()[0]
    assert saved == attacks
