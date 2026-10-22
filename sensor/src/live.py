"""Captura ao vivo: tcpdump -> fluxos -> IDSPipeline -> SQLite + alertas no terminal.

O tcpdump captura os pacotes (precisa de sudo) e escreve o pcap na saida
padrao; uma thread le os pacotes e o laco principal monta os fluxos,
encerra os inativos a cada segundo e classifica os que terminaram. A cada
segundo tambem checa a deteccao por volume (src.volume).
"""
import queue
import subprocess
import threading
import time
from datetime import datetime

from .flows import FlowMeter, read_stream

IDLE_TIMEOUT = 10   # s sem pacotes para encerrar um fluxo
TICK = 1.0          # s entre classificacoes


def default_interface():
    """Interface da rota padrao (ex.: enp1s0)."""
    out = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True).stdout.split()
    return out[out.index('dev') + 1] if 'dev' in out else 'any'


def tcpdump_command(interface):
    # -U: escreve cada pacote assim que chega; -Z root: evita a troca de usuario,
    # que falha ao escrever na saida padrao em alguns sistemas
    return ['sudo', 'tcpdump', '-i', interface, '-U', '-w', '-', '-Z', 'root', '-q',
            'ip and (tcp or udp)']


def ask_sudo():
    """Pede a senha do sudo antes de comecar, para nao misturar com os alertas."""
    print('A captura de pacotes precisa de permissao de administrador (sudo).')
    if subprocess.run(['sudo', '-v']).returncode != 0:
        raise SystemExit('Sem permissao de sudo; captura cancelada.')


def print_alerts(rows):
    """Agrupa os ataques do lote por tipo/origem/destino e imprime uma linha por grupo.

    Fluxos de ataques de volume ficam de fora: o alerta deles ja saiu em print_volume_alerts.
    """
    attacks = rows[rows['detected_by'] == 'modelo']
    if attacks.empty:
        return
    hora = datetime.now().strftime('%H:%M:%S')
    grupos = attacks.groupby(['attack_type', 'Src IP', 'Dst IP']).agg(
        fluxos=('attack_prob', 'size'), portas=('Dst Port', 'nunique'), prob=('attack_prob', 'mean'))
    for (tipo, src, dst), g in grupos.iterrows():
        print(f'\r[{hora}] ALERTA {tipo:<12} {src} -> {dst}  [modelo] '
              f'{int(g["fluxos"])} fluxo(s), {int(g["portas"])} porta(s), prob {g["prob"]:.2f}' + ' ' * 10)


def print_volume_alerts(alerts):
    """Imprime uma linha por alerta da deteccao por volume."""
    hora = datetime.now().strftime('%H:%M:%S')
    for a in alerts:
        origem = a['src_ip'] or f'{a["sources"]} origens'
        extra = f', {a["ports"]} porta(s)' if a['ports'] else ''
        print(f'\r[{hora}] ALERTA {a["type"]:<12} {origem} -> {a["dst_ip"]}  [volume] '
              f'{a["rate"]:,.0f} pacotes/s{extra}' + ' ' * 10)


class LiveCapture:
    """Le pacotes de um comando que escreve pcap na saida padrao e classifica os fluxos.

    `clock='wall'` usa o relogio do sistema para encerrar fluxos inativos (captura
    real); `clock='packet'` usa o horario do ultimo pacote (para testes com arquivos).
    """

    def __init__(self, command, detector, on_alert=print_alerts, on_volume=print_volume_alerts,
                 clock='wall', idle=IDLE_TIMEOUT):
        self.command, self.detector = command, detector
        self.on_alert, self.on_volume = on_alert, on_volume
        self.clock, self.idle_us = clock, int(idle * 1e6)
        self.meter = FlowMeter()
        self.last_ts = 0

    def _now_us(self):
        return int(time.time() * 1e6) if self.clock == 'wall' else self.last_ts

    def _classify(self, flows):
        rows = self.detector.process(flows)
        if rows is not None:
            self.on_alert(rows)

    def _check_volume(self):
        alerts = self.detector.check_volume(self._now_us())
        if alerts:
            self.on_volume(alerts)

    def _status(self):
        d = self.detector
        print(f'\r[ao vivo] fluxos: {d.total:,} | ataques: {d.attacks:,} | '
              f'fluxos abertos: {len(self.meter.flows):,}   ', end='', flush=True)

    def run(self, stop=None, duration=None):
        """Captura ate o comando terminar, `stop` ser sinalizado, `duration` segundos ou Ctrl+C."""
        proc = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        packets = queue.Queue(maxsize=100_000)
        errors = []

        def reader():
            try:
                for pkt in read_stream(proc.stdout):
                    packets.put(pkt)
            except Exception as exc:    # pcap invalido ou comando que falhou
                errors.append(exc)
            packets.put(None)

        threading.Thread(target=reader, daemon=True).start()
        deadline = time.monotonic() + duration if duration else None
        next_tick = time.monotonic() + TICK
        pending = []
        try:
            while True:
                try:
                    pkt = packets.get(timeout=0.2)
                except queue.Empty:
                    pkt = False
                if pkt is None:
                    break
                if pkt:
                    self.last_ts = pkt.ts
                    self.detector.observe(pkt)
                    pending += self.meter.process(pkt)
                if (stop and stop.is_set()) or (deadline and time.monotonic() > deadline):
                    break
                if time.monotonic() >= next_tick:
                    pending += self.meter.expire(self._now_us(), self.idle_us)
                    self._classify(pending)
                    pending = []
                    self._check_volume()
                    self._status()
                    next_tick = time.monotonic() + TICK
        except KeyboardInterrupt:
            pass
        finally:
            self._stop(proc)
            # pacotes que ja estavam na fila entram antes de encerrar os fluxos
            while True:
                try:
                    pkt = packets.get_nowait()
                except queue.Empty:
                    break
                if pkt:
                    self.last_ts = pkt.ts
                    self.detector.observe(pkt)
                    pending += self.meter.process(pkt)
            self._check_volume()
            self._classify(pending + self.meter.flush())
            self._status()
            print()

        stderr = proc.stderr.read().decode(errors='replace').strip()
        if proc.returncode not in (0, None, -2, -15) and self.detector.total == 0:
            raise SystemExit(f'A captura falhou:\n{stderr}')
        if errors and self.detector.total == 0:
            raise SystemExit(f'Erro ao ler os pacotes: {errors[0]}\n{stderr}')

    @staticmethod
    def _stop(proc):
        if proc.poll() is not None:
            return
        try:
            proc.terminate()
        except PermissionError:
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            # o tcpdump roda como root via sudo; o sudo repassa o sinal ao comando
            subprocess.run(['sudo', '-n', 'kill', '-TERM', str(proc.pid)], stderr=subprocess.DEVNULL)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                print(f'\nNao consegui encerrar o tcpdump (pid {proc.pid}); use: sudo kill {proc.pid}')
