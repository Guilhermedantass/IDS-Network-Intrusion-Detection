import sqlite3

from src import detect
from src.detect import Detector
from src.flows import SYN, Packet
from src.live import LiveCapture
from tests.test_flows import handshake_flow, write_pcap


def scan_packets():
    return [Packet(ts=2_000_000 + i * 10, src='10.0.0.9', dst='10.0.0.2', sport=40000, dport=1000 + i,
                   proto=6, payload=0, header=24, flags=SYN) for i in range(50)]


def test_live_capture_matches_file_mode(tmp_path):
    """O modo ao vivo (lendo um pcap continuo) classifica os mesmos fluxos que o modo arquivo."""
    pcap = tmp_path / 'captura.pcap'
    write_pcap(pcap, handshake_flow() + scan_packets())

    file_run = detect.run(pcap, tmp_path / 'arquivo.db')

    alerts = []
    detector = Detector('teste', tmp_path / 'ao_vivo.db')
    # `cat` faz o papel do `tcpdump -w -`; o relogio dos pacotes substitui o do sistema
    LiveCapture(['cat', str(pcap)], detector, on_alert=alerts.append, clock='packet').run()
    detector.close()

    def counts(db, run_id):
        conn = sqlite3.connect(db)
        return dict(conn.execute('SELECT attack_type, COUNT(*) FROM flows WHERE run_id = ? GROUP BY 1',
                                 (run_id,)).fetchall())

    assert counts(tmp_path / 'ao_vivo.db', detector.run_id) == counts(tmp_path / 'arquivo.db', file_run)
    assert detector.total == 51


def test_live_capture_reports_failed_command(tmp_path):
    detector = Detector('teste', tmp_path / 'ids.db')
    try:
        LiveCapture(['false'], detector, on_alert=lambda rows: None).run()
    except SystemExit as exc:
        assert 'falhou' in str(exc) or 'Erro' in str(exc)
    else:
        raise AssertionError('esperava SystemExit')
    finally:
        detector.close()


def test_live_capture_reports_volume_alerts(tmp_path):
    pcap = tmp_path / 'scan.pcap'
    write_pcap(pcap, [Packet(ts=1_700_000_000_000_000 + i * 1000, src='10.0.0.9', dst='10.0.0.2',
                             sport=40000, dport=i + 1, proto=6, payload=0, header=24, flags=SYN)
                      for i in range(300)])
    volume = []
    detector = Detector('teste', tmp_path / 'ids.db')
    LiveCapture(['cat', str(pcap)], detector, on_alert=lambda rows: None, on_volume=volume.extend,
                clock='packet').run()
    detector.close()
    assert [(a['type'], a['ports']) for a in volume] == [('PortScan', 300)]
    assert detector.volume_counts == {'PortScan': 1}
