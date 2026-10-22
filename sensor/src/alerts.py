"""Alertas no formato da API (POST /api/alerts) e envio por HTTP em segundo plano.

Um alerta resume um ataque (tipo + origem + destino), e nao um fluxo: um flood
tem milhares de fluxos e viraria milhares de requisicoes. Formato (contrato com
a API em Java, campos em camelCase):

    {"sensor": "pc-casa", "alerts": [{"ts": "2026-10-22T13:33:19Z", "type": "SYN Flood",
      "detectedBy": "volume", "srcIp": "127.0.0.1", "dstIp": "127.0.0.1", "dstPort": 9,
      "protocol": "TCP", "flows": null, "packets": 1800, "rate": 180.0, "ports": 1,
      "sources": null, "probability": null}]}

Campos que nao se aplicam vao como null: `flows` e `probability` vem do modelo;
`packets`, `rate` e `sources` vem da deteccao por volume.
"""
import json
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone

PROTOCOLS = {6: 'TCP', 17: 'UDP'}
MAX_BATCH = 500         # alertas por requisicao
MAX_BACKOFF = 30        # s entre tentativas com a API fora do ar


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def model_alerts(rows):
    """Agrupa os ataques do modelo de um lote (DataFrame de Detector.process) em alertas.

    Fluxos de ataques de volume ficam de fora: o alerta deles sai em volume_alerts.
    """
    attacks = rows[rows['detected_by'] == 'modelo']
    if attacks.empty:
        return []
    grupos = attacks.groupby(['attack_type', 'Src IP', 'Dst IP', 'Protocol']).agg(
        ts=('Timestamp', 'min'), flows=('attack_prob', 'size'), ports=('Dst Port', 'nunique'),
        port=('Dst Port', 'first'), prob=('attack_prob', 'mean'))
    return [{
        'ts': _iso(g['ts']), 'type': tipo, 'detectedBy': 'modelo',
        'srcIp': src, 'dstIp': dst, 'dstPort': int(g['port']) if g['ports'] == 1 else None,
        'protocol': PROTOCOLS.get(int(proto), str(proto)),
        'flows': int(g['flows']), 'packets': None, 'rate': None, 'ports': int(g['ports']),
        'sources': None, 'probability': round(float(g['prob']), 4),
    } for (tipo, src, dst, proto), g in grupos.iterrows()]


def volume_alerts(alerts):
    """Converte os alertas de src.volume para o formato da API."""
    return [{
        'ts': _iso(a['ts']), 'type': a['type'], 'detectedBy': 'volume',
        'srcIp': a['src_ip'], 'dstIp': a['dst_ip'], 'dstPort': a['dst_port'],
        'protocol': PROTOCOLS[a['protocol']],
        'flows': None, 'packets': a['packets'], 'rate': round(a['rate'], 1), 'ports': a['ports'],
        'sources': a['sources'], 'probability': None,
    } for a in alerts]


class AlertSender:
    """Envia alertas para a API em uma thread propria, sem travar a captura.

    Os alertas ficam numa fila; com a API fora do ar, o envio e repetido com
    espera crescente (ate MAX_BACKOFF s) e, se a fila encher, os mais antigos
    sao descartados. Respostas 4xx (alerta recusado pela API) nao sao repetidas.
    """

    def __init__(self, base_url, sensor, max_queue=10_000, timeout=5, log=print):
        self.url = base_url.rstrip('/') + '/api/alerts'
        self.sensor, self.timeout, self.log = sensor, timeout, log
        self.queue = deque(maxlen=max_queue)
        self.cond = threading.Condition()
        self.deadline = None    # definido no close: ate quando tentar enviar o resto
        self.sent = self.dropped = 0
        self.online = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def send(self, alerts):
        if not alerts:
            return
        with self.cond:
            self.dropped += max(0, len(self.queue) + len(alerts) - self.queue.maxlen)
            self.queue.extend(alerts)
            self.cond.notify()

    def _post(self, batch):
        body = json.dumps({'sensor': self.sensor, 'alerts': batch}).encode()
        req = urllib.request.Request(self.url, data=body, method='POST',
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=self.timeout):
            pass

    def _run(self):
        backoff = 1
        while True:
            with self.cond:
                while not self.queue and self.deadline is None:
                    self.cond.wait()
                if not self.queue:
                    return
                batch = [self.queue.popleft() for _ in range(min(MAX_BATCH, len(self.queue)))]
            try:
                self._post(batch)
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    self.log(f'\nAPI recusou {len(batch)} alerta(s): HTTP {exc.code} {exc.reason}')
                    self.dropped += len(batch)
                    continue
                error = f'HTTP {exc.code}'
            except (urllib.error.URLError, OSError) as exc:
                error = str(getattr(exc, 'reason', exc))
            else:
                self.sent += len(batch)
                backoff = 1
                if not self.online:
                    self.online = True
                    self.log(f'\nAPI de volta ({self.url}); enviando os alertas da fila')
                continue
            # falhou: devolve o lote para o comeco da fila e espera antes de tentar de novo
            with self.cond:
                self.queue.extendleft(reversed(batch))
                if self.online:
                    self.online = False
                    self.log(f'\nAPI indisponivel ({self.url}: {error}); os alertas ficam na fila')
                if self.deadline is not None:
                    restante = self.deadline - time.monotonic()
                    if restante <= 0:
                        return
                    self.cond.wait(min(backoff, restante))
                else:
                    self.cond.wait(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)

    def close(self, timeout=5):
        """Tenta enviar o que sobrou na fila por ate `timeout` s."""
        with self.cond:
            self.deadline = time.monotonic() + timeout
            self.cond.notify()
        self.thread.join(timeout)
        if self.queue:
            self.log(f'{len(self.queue)} alerta(s) nao enviado(s) para a API')
