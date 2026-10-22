import sqlite3

from src import detect
from src.flows import ACK, SYN, Packet
from src.volume import Limits, VolumeDetector
from tests.test_flows import write_pcap

T0 = 1_700_000_000_000_000  # us


def syn(ts, src='10.0.0.9', dst='10.0.0.2', sport=40000, dport=80, flags=SYN):
    return Packet(ts=ts, src=src, dst=dst, sport=sport, dport=dport, proto=6,
                  payload=0, header=40, flags=flags)


def udp(ts, src='10.0.0.9', dst='10.0.0.2', sport=40000, dport=53):
    return Packet(ts=ts, src=src, dst=dst, sport=sport, dport=dport, proto=17, payload=64, header=8)


def run(packets, limits=None):
    vol = VolumeDetector(limits)
    for p in packets:
        vol.add(p)
    return vol, vol.check(max(p.ts for p in packets))


def types(alerts):
    return sorted(a['type'] for a in alerts)


def test_syn_flood():
    # 2000 SYNs em 5 s = 200/s, acima de 100/s na janela de 10 s
    _, alerts = run([syn(T0 + i * 2500, sport=10000 + i % 50000) for i in range(2000)])
    assert types(alerts) == ['SYN Flood']
    assert alerts[0]['src_ip'] == '10.0.0.9' and alerts[0]['packets'] == 2000


def test_normal_traffic_has_no_alert():
    # navegacao: algumas conexoes, respostas SYN+ACK e muito trafego UDP de ida e volta
    packets = [syn(T0 + i * 100_000, sport=50000 + i) for i in range(30)]
    packets += [syn(T0 + i * 100_000, src='10.0.0.2', dst='10.0.0.9', sport=80, dport=50000 + i,
                    flags=SYN | ACK) for i in range(30)]
    packets += [udp(T0 + i * 200, dport=443) for i in range(30_000)]
    packets += [udp(T0 + i * 400, src='10.0.0.2', dst='10.0.0.9', sport=443, dport=40000)
                for i in range(15_000)]
    _, alerts = run(packets)
    assert alerts == []


def test_ddos_from_many_sources():
    # 50 origens com 50 SYN/s cada: nenhuma passa do limite sozinha, mas o destino recebe 2500/s
    packets = [syn(T0 + i * 400, src=f'10.1.0.{i % 50}', sport=10000 + i) for i in range(25_000)]
    _, alerts = run(packets)
    assert types(alerts) == ['DDoS']
    assert alerts[0]['src_ip'] is None and alerts[0]['sources'] == 50


def test_udp_flood_needs_one_way_traffic():
    flood = [udp(T0 + i * 100) for i in range(50_000)]  # 10.000 pacotes/s por 5 s
    _, alerts = run(flood)
    assert types(alerts) == ['UDP Flood']
    resposta = [udp(T0 + i * 100, src='10.0.0.2', dst='10.0.0.9', sport=53, dport=40000) for i in range(25_000)]
    _, alerts = run(flood + resposta)
    assert alerts == []


def test_udp_flood_on_loopback():
    # na interface lo origem e destino sao o mesmo IP: o flood nao pode contar como resposta dele mesmo
    flood = [udp(T0 + i * 100, src='127.0.0.1', dst='127.0.0.1', sport=40000, dport=9) for i in range(50_000)]
    _, alerts = run(flood)
    assert types(alerts) == ['UDP Flood']
    resposta = [udp(T0 + i * 100, src='127.0.0.1', dst='127.0.0.1', sport=9, dport=40000) for i in range(25_000)]
    _, alerts = run(flood + resposta)
    assert alerts == []


def test_port_scan():
    _, alerts = run([syn(T0 + i * 100, dport=i + 1) for i in range(500)])
    assert types(alerts) == ['PortScan']
    assert alerts[0]['ports'] == 500


def test_cooldown_and_window():
    vol = VolumeDetector(Limits(cooldown=30))
    for i in range(500):
        vol.add(syn(T0 + i * 100, dport=i + 1))
    assert len(vol.check(T0 + 1_000_000)) == 1
    assert vol.check(T0 + 2_000_000) == []              # mesmo alerta dentro do cooldown
    assert vol.check(T0 + 40_000_000) == []             # o scan ja saiu da janela
    assert vol.buckets == {}


def test_file_mode_saves_volume_alerts(tmp_path):
    pcap, db = tmp_path / 'scan.pcap', tmp_path / 'ids.db'
    write_pcap(pcap, [syn(T0 + i * 1000, dport=i + 1) for i in range(300)])
    run_id = detect.run(pcap, db)
    rows = sqlite3.connect(db).execute(
        'SELECT type, src_ip, dst_ip, ports FROM volume_alerts WHERE run_id = ?', (run_id,)).fetchall()
    assert rows == [('PortScan', '10.0.0.9', '10.0.0.2', 300)]
