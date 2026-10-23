"""Bloqueio de IPs no firewall do Linux (nftables): a parte de resposta do sensor (IPS).

O sensor cria uma tabela propria, separada das regras do sistema (ufw, firewalld, Docker):

    table inet ids {
        set bloqueados4 { type ipv4_addr; }
        set bloqueados6 { type ipv6_addr; }
        chain entrada { type filter hook input priority -10; ip saddr @bloqueados4 drop; ... }
        chain repasse { type filter hook forward priority -10; ... }   (trafego para containers e VMs)
    }

Bloquear ou desbloquear = por ou tirar um IP do set; as regras nao mudam. Um drop em qualquer tabela e
final, entao o bloqueio vale mesmo se o ufw aceitar a porta. A tabela e apagada ao desligar o servico e
ao ligar de novo (sobra de um servico que caiu); nada fica bloqueado para sempre por engano.

Nunca bloqueia (protegidos): loopback, os IPs da propria maquina, o gateway e o host da API (bloquear a
API cortaria o heartbeat e, com ele, o desbloqueio pelo dashboard).

Precisa de root: roda `sudo -n nft`, aproveitando o sudo pedido ao ligar o servico.
"""
import ipaddress
import json
import socket
import subprocess
from urllib.parse import urlparse

TABLE = 'inet ids'

SETUP = f"""
table {TABLE} {{
    set bloqueados4 {{ type ipv4_addr; }}
    set bloqueados6 {{ type ipv6_addr; }}
    chain entrada {{
        type filter hook input priority -10; policy accept;
        ip saddr @bloqueados4 drop
        ip6 saddr @bloqueados6 drop
    }}
    chain repasse {{
        type filter hook forward priority -10; policy accept;
        ip saddr @bloqueados4 drop
        ip6 saddr @bloqueados6 drop
    }}
}}
"""


class FirewallError(Exception):
    pass


def run_nft(script):
    """Executa um script do nft de uma vez so (atomico: ou aplica tudo ou nada)."""
    try:
        proc = subprocess.run(['sudo', '-n', 'nft', '-f', '-'], input=script, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise FirewallError(f'comando nao encontrado: {exc.filename}') from exc
    if proc.returncode != 0:
        raise FirewallError(proc.stderr.strip() or f'nft saiu com codigo {proc.returncode}')


def _ip_json(*args):
    try:
        out = subprocess.run(['ip', '-j', *args], capture_output=True, text=True, timeout=5).stdout
        return json.loads(out or '[]')
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []


def protected_ips(api=None):
    """IPs que nunca podem ser bloqueados: os da propria maquina, os gateways e o host da API."""
    ips = set()
    for iface in _ip_json('addr'):
        ips.update(a['local'] for a in iface.get('addr_info', []) if 'local' in a)
    for family in ('-4', '-6'):
        ips.update(r['gateway'] for r in _ip_json(family, 'route', 'show', 'default') if 'gateway' in r)
    host = urlparse(api).hostname if api else None
    if host:
        try:
            ips.update(info[4][0] for info in socket.getaddrinfo(host, None))
        except OSError:
            pass
    return {_normalize(ip) for ip in ips if _normalize(ip)}


def _normalize(ip):
    """IP no formato canonico, ou None se nao for um IP (tambem impede injetar texto no script do nft)."""
    try:
        return str(ipaddress.ip_address(str(ip).split('%')[0]))   # fe80::1%eth0 -> fe80::1
    except ValueError:
        return None


class Firewall:
    """Mantem o set de bloqueados igual ao pedido pelo dashboard.

    `run` troca o `sudo nft` por outra funcao (nos testes, uma que so guarda os scripts).
    `protected` e chamada a cada `refresh()`: o IP da maquina pode mudar (DHCP).
    """

    def __init__(self, protected=lambda: set(), run=run_nft, log=print):
        self._protected_fn, self.run, self.log = protected, run, log
        self.protected = set()
        self.blocked = set()
        self.error = None
        self.ready = False      # tabela criada?

    def refresh(self):
        self.protected = self._protected_fn()

    def is_protected(self, ip):
        addr = ipaddress.ip_address(ip)
        return addr.is_loopback or addr.is_unspecified or addr.is_multicast or ip in self.protected

    def reset(self):
        """Apaga a tabela (sobra de um servico que caiu). Sem tabela, o nft da erro: tudo bem."""
        try:
            self.run(f'delete table {TABLE}\n')
        except FirewallError:
            pass
        self.ready, self.blocked = False, set()

    def sync(self, wanted):
        """Bloqueia o que falta e desbloqueia o que saiu da lista. Erros ficam em `self.error`."""
        problems, want = [], set()
        for raw in wanted:
            ip = _normalize(raw)
            if ip is None:
                problems.append(f'{raw} nao e um IP')
            elif self.is_protected(ip):
                problems.append(f'{ip} e protegido (proprio PC, gateway ou API)')
            else:
                want.add(ip)

        add, remove = sorted(want - self.blocked), sorted(self.blocked - want)
        if add or remove:
            script = '' if self.ready else SETUP
            script += ''.join(f'add element {TABLE} {_set_of(ip)} {{ {ip} }}\n' for ip in add)
            script += ''.join(f'delete element {TABLE} {_set_of(ip)} {{ {ip} }}\n' for ip in remove)
            try:
                self.run(script)
            except FirewallError as exc:
                problems.append(f'nftables: {exc}')
            else:
                self.ready, self.blocked = True, want
                for ip in add:
                    self.log(f'Bloqueado: {ip}')
                for ip in remove:
                    self.log(f'Desbloqueado: {ip}')

        error = '; '.join(problems) or None
        if error and error != self.error:
            self.log(f'Bloqueio: {error}')
        self.error = error

    def close(self):
        if self.ready:
            self.reset()


def _set_of(ip):
    return 'bloqueados6' if ':' in ip else 'bloqueados4'
