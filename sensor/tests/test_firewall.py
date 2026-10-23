import pytest

from src import firewall
from src.firewall import Firewall, FirewallError


def make_firewall(protected=(), fail=None):
    """Firewall com um nft falso: guarda os scripts; `fail` faz a proxima chamada dar erro."""
    scripts = []

    def run(script):
        if fail and fail[0]:
            raise FirewallError(fail.pop(0))
        scripts.append(script)

    fw = Firewall(protected=lambda: set(protected), run=run, log=lambda m: None)
    fw.refresh()
    return fw, scripts


def test_primeiro_bloqueio_cria_a_tabela_e_depois_so_mexe_no_set():
    fw, scripts = make_firewall()
    fw.sync(['10.0.0.5'])
    assert 'table inet ids' in scripts[0] and 'hook input' in scripts[0]
    assert 'add element inet ids bloqueados4 { 10.0.0.5 }' in scripts[0]

    fw.sync(['10.0.0.5', '2001:db8::7'])
    assert scripts[1] == 'add element inet ids bloqueados6 { 2001:db8::7 }\n'

    fw.sync(['2001:db8::7'])
    assert scripts[2] == 'delete element inet ids bloqueados4 { 10.0.0.5 }\n'
    assert fw.blocked == {'2001:db8::7'} and fw.error is None


def test_sem_mudanca_nao_chama_o_nft():
    fw, scripts = make_firewall()
    fw.sync(['10.0.0.5'])
    fw.sync(['10.0.0.5'])
    assert len(scripts) == 1


@pytest.mark.parametrize('ip', ['127.0.0.1', '::1', '0.0.0.0', '224.0.0.1', '192.168.0.1'])
def test_nunca_bloqueia_protegidos(ip):
    fw, scripts = make_firewall(protected={'192.168.0.1'})
    fw.sync([ip])
    assert fw.blocked == set() and scripts == []
    assert 'protegido' in fw.error


def test_texto_que_nao_e_ip_nao_chega_no_nft():
    fw, scripts = make_firewall()
    fw.sync(['1.2.3.4 }; flush ruleset; {'])
    assert scripts == [] and 'nao e um IP' in fw.error


def test_erro_do_nft_nao_muda_o_estado_e_tenta_de_novo():
    fw, scripts = make_firewall(fail=['sudo: a password is required'])
    fw.sync(['10.0.0.5'])
    assert fw.blocked == set() and 'password' in fw.error
    fw.sync(['10.0.0.5'])                           # proximo heartbeat: tenta de novo (e cria a tabela)
    assert fw.blocked == {'10.0.0.5'} and fw.error is None
    assert 'table inet ids' in scripts[0]


def test_close_apaga_a_tabela():
    fw, scripts = make_firewall()
    fw.close()
    assert scripts == []                            # nunca criou: nao tem o que apagar
    fw.sync(['10.0.0.5'])
    fw.close()
    assert scripts[-1] == 'delete table inet ids\n' and fw.blocked == set()


def test_protegidos_vem_do_ip_e_da_api(monkeypatch):
    def fake_ip_json(*args):
        if args == ('addr',):
            return [{'addr_info': [{'local': '127.0.0.1'}, {'local': '192.168.0.10'}, {'local': 'fe80::1%eth0'}]}]
        if args[0] == '-4':
            return [{'gateway': '192.168.0.1'}]
        return []
    monkeypatch.setattr(firewall, '_ip_json', fake_ip_json)
    monkeypatch.setattr(firewall.socket, 'getaddrinfo', lambda host, port: [(None, None, None, None, ('10.9.9.9', 0))])
    assert firewall.protected_ips('http://api.local:8080') == {'127.0.0.1', '192.168.0.10', 'fe80::1', '192.168.0.1',
                                                               '10.9.9.9'}
