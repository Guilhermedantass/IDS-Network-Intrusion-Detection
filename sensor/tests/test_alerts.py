import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src import alerts, detect
from src.alerts import AlertSender
from tests.test_flows import write_pcap
from tests.test_volume import T0, syn

FIELDS = {'ts', 'type', 'detectedBy', 'srcIp', 'dstIp', 'dstPort', 'protocol', 'flows', 'packets',
          'rate', 'ports', 'sources', 'probability'}


@pytest.fixture
def api():
    """API falsa: guarda os corpos recebidos e responde com os codigos de `api.codes` (depois 201)."""
    received, codes = [], []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            code = codes.pop(0) if codes else 201
            if code < 300:
                received.append((self.path, body))
            self.send_response(code)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    server.url = f'http://127.0.0.1:{server.server_port}'
    server.received, server.codes = received, codes
    yield server
    server.shutdown()


def sent_alerts(api):
    return [a for _, body in api.received for a in body['alerts']]


def test_file_mode_sends_alerts(api, tmp_path):
    pcap = tmp_path / 'scan.pcap'
    write_pcap(pcap, [syn(T0 + i * 1000, dport=i + 1) for i in range(300)])
    sender = AlertSender(api.url, 'sensor-teste', log=lambda msg: None)
    detect.run(pcap, tmp_path / 'ids.db', sender=sender)
    sender.close()

    path, body = api.received[0]
    assert path == '/api/alerts' and body['sensor'] == 'sensor-teste'
    [alerta] = sent_alerts(api)
    assert set(alerta) == FIELDS
    assert alerta['type'] == 'PortScan' and alerta['detectedBy'] == 'volume'
    assert alerta['srcIp'] == '10.0.0.9' and alerta['protocol'] == 'TCP' and alerta['ports'] == 300
    assert alerta['ts'].endswith('Z') and alerta['flows'] is None and alerta['probability'] is None
    assert sender.sent == 1


def test_model_alerts_group_flows():
    import pandas as pd
    rows = pd.DataFrame({
        'Timestamp': [T0 / 1e6 + 1, T0 / 1e6], 'Src IP': ['10.0.0.9'] * 2, 'Dst IP': ['10.0.0.2'] * 2,
        'Protocol': [6, 6], 'Dst Port': [80, 80], 'attack_prob': [0.9, 0.7],
        'attack_type': ['WebAttack'] * 2, 'detected_by': ['modelo', 'modelo'],
    })
    [alerta] = alerts.model_alerts(rows)
    assert set(alerta) == FIELDS
    assert (alerta['flows'], alerta['dstPort'], alerta['probability']) == (2, 80, 0.8)
    assert alerta['ts'] == '2023-11-14T22:13:20Z'
    # fluxos de ataque de volume nao geram alerta do modelo
    assert alerts.model_alerts(rows.assign(detected_by='modelo+volume')) == []


def test_sender_retries_when_api_fails(api):
    api.codes += [503, 503]
    logs = []
    sender = AlertSender(api.url, 's', log=logs.append)
    sender.send([{'type': 'teste', 'n': i} for i in range(3)])
    sender.close(timeout=10)
    assert [a['n'] for a in sent_alerts(api)] == [0, 1, 2]     # nada perdido, na ordem
    assert any('indisponivel' in m for m in logs) and any('de volta' in m for m in logs)


def test_sender_drops_rejected_alerts(api):
    api.codes.append(400)
    sender = AlertSender(api.url, 's', log=lambda msg: None)
    sender.send([{'type': 'invalido'}])
    sender.close()
    assert api.received == [] and sender.dropped == 1


def test_sender_keeps_queue_when_api_is_down():
    logs = []
    sender = AlertSender('http://127.0.0.1:9', 's', timeout=1, log=logs.append)    # porta fechada
    sender.send([{'type': 'teste'}])
    sender.close(timeout=2)
    assert sender.sent == 0 and len(sender.queue) == 1
    assert any('nao enviado' in m for m in logs)
