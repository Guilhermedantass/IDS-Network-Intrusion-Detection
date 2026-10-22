"""Servico do sensor: fica ligado e obedece o dashboard (./ids servico --api URL).

A cada HEARTBEAT s manda o estado para a API (POST /api/sensors/heartbeat) e recebe de
volta o estado desejado: capturar ou nao, e em qual interface. Se for diferente do atual,
liga, desliga ou troca a captura. O sensor nao abre porta nenhuma: ele chama a API, nunca
o contrario (funciona com o sensor em outra maquina, atras de NAT).

Contrato (a API em Java depende dele):
    enviado  {"sensor", "capturing", "interface", "startedAt", "flows", "attacks", "alertsSent",
              "interfaces": [...], "error"}
    recebido {"capture": true|false, "interface": "lo"|null}   (null = interface padrao)

sudo: o tcpdump precisa de root. O servico pede a senha uma vez ao ligar (sudo -v) e renova
a permissao a cada SUDO_REFRESH s (sudo -n -v), entao a captura pode comecar a qualquer hora.
"""
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .alerts import AlertSender
from .detect import Detector
from .live import LiveCapture, ask_sudo, default_interface, tcpdump_command

HEARTBEAT = 5       # s entre um "estou vivo" e o proximo
SUDO_REFRESH = 60   # s entre as renovacoes do sudo (o padrao do sistema expira em 15 min)


def list_interfaces():
    """Interfaces de rede da maquina, sem as virtuais do Docker (veth*)."""
    try:
        names = os.listdir('/sys/class/net')
    except OSError:
        return []
    return sorted(n for n in names if not n.startswith('veth'))


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


class Capture:
    """Uma captura ao vivo rodando numa thread, ate `finish()` ou um erro.

    `command` troca o tcpdump por outro comando que escreve pcap na saida padrao (nos testes, `cat arquivo.pcap`).
    """

    def __init__(self, interface, api, sensor, db_path, log=print, command=None):
        self.interface, self.db_path = interface, db_path
        self.command = command or tcpdump_command(interface)
        self.started_at = time.time()
        self.error = None
        self.sender = AlertSender(api, sensor, log=log)
        self.detector = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            # o SQLite so aceita a conexao na thread que a criou: o Detector (que abre o banco) nasce aqui dentro
            self.detector = Detector(f'servico ({self.interface})', self.db_path, sender=self.sender)
            LiveCapture(self.command, self.detector).run(stop=self._stop)
        except SystemExit as exc:      # o LiveCapture avisa falhas (tcpdump, sudo) com SystemExit
            self.error = str(exc)
        except Exception as exc:
            self.error = f'{type(exc).__name__}: {exc}'
        finally:
            if self.detector:
                self.detector.close()
            self.sender.close()

    @property
    def running(self):
        return self._thread.is_alive()

    def finish(self):
        self._stop.set()
        self._thread.join(timeout=15)

    def counters(self):
        d = self.detector   # None nos primeiros segundos, enquanto o modelo carrega
        return {'flows': d.total if d else 0, 'attacks': d.attacks if d else 0, 'alertsSent': self.sender.sent}


class Service:
    """Mantem a captura igual ao estado desejado que a API devolve em cada heartbeat."""

    def __init__(self, api, sensor, db_path, capture_factory=Capture, post=None, log=print):
        self.api, self.sensor, self.db_path = api.rstrip('/'), sensor, db_path
        self.capture_factory, self.log = capture_factory, log
        self.post = post or self._post
        self.capture = None
        self.last = None            # contadores e erro da ultima captura, para seguir aparecendo depois
        self.failed_for = None      # desejado que falhou: nao tenta de novo ate o dashboard mudar
        self.online = None

    # ---- estado

    def status(self):
        c = self.capture
        if c and not c.running:     # a captura caiu sozinha (erro do tcpdump, por exemplo)
            self._finish_capture()
            c = None
        body = {
            'sensor': self.sensor,
            'capturing': c is not None,
            'interface': c.interface if c else None,
            'startedAt': _iso(c.started_at) if c else None,
            'flows': 0, 'attacks': 0, 'alertsSent': 0,
            'interfaces': list_interfaces(),
            'error': None,
        }
        if c:
            body.update(c.counters())
        elif self.last:
            body.update(self.last)
        return body

    # ---- aplicar o desejado

    def apply(self, desired):
        want = bool(desired.get('capture'))
        interface = desired.get('interface') or default_interface()
        key = (want, interface)
        if self.failed_for and self.failed_for != key:
            self.failed_for = None      # o dashboard mudou o pedido: pode tentar de novo
        current = self.capture

        if current and (not want or current.interface != interface):
            self.log(f'Parando a captura em {current.interface}')
            current.finish()
            self._finish_capture()
            current = None
        if want and current is None and self.failed_for != key:
            self.log(f'Iniciando a captura em {interface}')
            try:
                self.capture = self.capture_factory(interface, self.api, self.sensor, self.db_path, log=self.log)
                self.last = None
            except Exception as exc:
                self.last = {'error': f'Nao foi possivel iniciar: {exc}'}
                self.failed_for = key

    def _finish_capture(self):
        c, self.capture = self.capture, None
        self.last = {**c.counters(), 'error': c.error}
        if c.error:
            self.log(f'A captura em {c.interface} parou com erro: {c.error}')
            self.failed_for = (True, c.interface)

    # ---- conversa com a API

    def _post(self, body):
        req = urllib.request.Request(f'{self.api}/api/sensors/heartbeat', data=json.dumps(body).encode(),
                                     method='POST', headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())

    def tick(self):
        """Um heartbeat: manda o estado e aplica o desejado. Com a API fora, mantem o que esta."""
        try:
            desired = self.post(self.status())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            if self.online is not False:
                self.log(f'API indisponivel ({self.api}): {getattr(exc, "reason", exc)}; mantendo o estado atual')
            self.online = False
            return
        if self.online is False:
            self.log('API de volta')
        self.online = True
        self.apply(desired)

    def stop(self):
        if self.capture:
            self.capture.finish()
            self._finish_capture()


def keep_sudo(stop, log=print):
    """Renova o sudo em segundo plano; avisa uma vez se ele expirar."""
    while not stop.wait(SUDO_REFRESH):
        if subprocess.run(['sudo', '-n', '-v'], stderr=subprocess.DEVNULL).returncode != 0:
            log('A permissao do sudo expirou: reinicie o servico para iniciar novas capturas.')
            return


def run(api, sensor, db_path):
    ask_sudo()
    stop = threading.Event()
    threading.Thread(target=keep_sudo, args=(stop,), daemon=True).start()
    service = Service(api, sensor, db_path)
    print(f'Servico do sensor "{sensor}" ligado. Controle pelo dashboard (pagina Sensores). Ctrl+C para desligar.')
    try:
        while True:
            service.tick()
            time.sleep(HEARTBEAT)
    except KeyboardInterrupt:
        print('\nDesligando...')
    finally:
        stop.set()
        service.stop()
