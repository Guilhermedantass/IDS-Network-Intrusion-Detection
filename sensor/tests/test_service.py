import urllib.error

from src import service
from src.firewall import Firewall
from src.service import Service


class FakeCapture:
    """Captura falsa: nao roda tcpdump; `fail` simula uma captura que cai sozinha com erro."""
    created = []

    def __init__(self, interface, api, sensor, db_path, log=print):
        self.interface, self.started_at, self.error = interface, 1_700_000_000, None
        self.running, self.finished = True, False
        FakeCapture.created.append(self)

    def finish(self):
        self.running, self.finished = False, True

    def fail(self, error):
        self.running, self.error = False, error

    def counters(self):
        return {'flows': 10, 'attacks': 2, 'alertsSent': 1}


def make_service(responses):
    """Servico com API falsa: cada tick devolve o proximo desejado de `responses` (ou levanta, se for excecao)."""
    FakeCapture.created = []
    sent = []

    def post(body):
        sent.append(body)
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    firewall = Firewall(protected=lambda: {'192.168.0.1'}, run=lambda script: None, log=lambda m: None)
    svc = Service('http://api', 'sensor-teste', ':memory:', capture_factory=FakeCapture, post=post,
                  firewall=firewall, log=lambda m: None)
    return svc, sent


def test_parado_ate_a_api_mandar_capturar():
    svc, sent = make_service([{'capture': False, 'interface': None}, {'capture': True, 'interface': 'lo'}])
    svc.tick()
    assert svc.capture is None
    assert sent[0]['capturing'] is False and sent[0]['sensor'] == 'sensor-teste'

    svc.tick()
    assert svc.capture.interface == 'lo'


def test_heartbeat_leva_o_estado_da_captura():
    svc, sent = make_service([{'capture': True, 'interface': 'lo'}, {'capture': True, 'interface': 'lo'}])
    svc.tick()
    svc.tick()
    body = sent[1]
    assert body['capturing'] is True and body['interface'] == 'lo'
    assert body['flows'] == 10 and body['attacks'] == 2 and body['alertsSent'] == 1
    assert body['startedAt'].endswith('Z')
    assert set(body) == {'sensor', 'capturing', 'interface', 'startedAt', 'flows', 'attacks', 'alertsSent',
                         'interfaces', 'error', 'blocked', 'protected', 'blockError'}


def test_parar_e_trocar_de_interface():
    svc, _ = make_service([{'capture': True, 'interface': 'lo'}, {'capture': True, 'interface': 'eth9'},
                           {'capture': False, 'interface': 'eth9'}])
    svc.tick()
    lo = svc.capture
    svc.tick()
    assert lo.finished and svc.capture.interface == 'eth9'
    svc.tick()
    assert svc.capture is None
    assert len(FakeCapture.created) == 2


def test_api_fora_mantem_o_estado():
    svc, _ = make_service([{'capture': True, 'interface': 'lo'}, urllib.error.URLError('recusado')])
    svc.tick()
    svc.tick()
    assert svc.capture is not None and svc.capture.running


def test_captura_com_erro_nao_fica_tentando_de_novo():
    svc, sent = make_service([{'capture': True, 'interface': 'lo'}, {'capture': True, 'interface': 'lo'},
                              {'capture': True, 'interface': 'lo'}, {'capture': False, 'interface': 'lo'},
                              {'capture': True, 'interface': 'lo'}])
    svc.tick()
    svc.capture.fail('tcpdump: lo: permissao negada')
    svc.tick()                                      # avisa o erro e nao tenta de novo
    assert sent[1]['capturing'] is False and 'permissao negada' in sent[1]['error']
    svc.tick()
    assert len(FakeCapture.created) == 1
    svc.tick()                                      # o dashboard mandou parar...
    svc.tick()                                      # ...e iniciar de novo: agora tenta
    assert len(FakeCapture.created) == 2


def test_bloqueios_seguem_o_desejado():
    svc, sent = make_service([{'capture': False, 'interface': None, 'blocked': ['10.0.0.5', '192.168.0.1']},
                              {'capture': False, 'interface': None},
                              {'capture': False, 'interface': None, 'blocked': []}])
    svc.tick()
    assert svc.firewall.blocked == {'10.0.0.5'}
    svc.tick()                                      # sem "blocked" na resposta: nao mexe
    body = sent[1]
    assert body['blocked'] == ['10.0.0.5'] and body['protected'] == ['192.168.0.1']
    assert '192.168.0.1 e protegido' in body['blockError']
    svc.tick()
    assert svc.firewall.blocked == set()


def test_interfaces_sem_as_do_docker(monkeypatch):
    monkeypatch.setattr(service.os, 'listdir', lambda path: ['veth12ab', 'lo', 'enp1s0', 'docker0'])
    assert service.list_interfaces() == ['docker0', 'enp1s0', 'lo']


def test_captura_de_verdade_grava_e_conta_na_thread_dela(tmp_path):
    """Captura real (Detector, SQLite, LiveCapture) lendo um pcap com cat no lugar do tcpdump.

    Pega o erro do SQLite usado fora da thread que abriu a conexao, que a captura falsa nao pega.
    """
    from src.service import Capture
    from tests.test_flows import write_pcap
    from tests.test_volume import T0, syn

    pcap = tmp_path / 'scan.pcap'
    write_pcap(pcap, [syn(T0 + i * 1000, dport=i + 1) for i in range(300)])
    cap = Capture('lo', 'http://127.0.0.1:9', 'sensor-teste', tmp_path / 'ids.db', log=lambda m: None,
                  command=['cat', str(pcap)])
    cap._thread.join(timeout=60)

    assert not cap.running
    assert cap.error is None
    assert cap.counters()['flows'] == 300
