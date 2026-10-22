"""Classificacao de fluxos e gravacao no SQLite, usada pelo modo arquivo e pelo ao vivo.

Cada fluxo recebe um tipo so. Se ele faz parte de um ataque de volume ativo
(src.volume), o tipo do volume vence o do modelo: o modelo olha um fluxo por vez
e chama um SYN flood de PortScan e um UDP flood de BENIGN. O tipo do modelo fica
em `model_type` e `detected_by` diz quem detectou (modelo, volume ou os dois).
"""
import time
from collections import Counter

import numpy as np
import pandas as pd

from . import storage
from .alerts import model_alerts, volume_alerts
from .data import BENIGN
from .flows import FlowMeter, read_pcap
from .pipeline import IDSPipeline
from .volume import PROTOCOL, VOLUME_TYPES, VolumeDetector


def model_features(ids):
    return list(dict.fromkeys(ids.binary_meta['features'] + ids.attack_meta['features']))


class Detector:
    """Classifica lotes de fluxos com o IDSPipeline e grava tudo em uma execucao (run) do banco.

    Tambem soma os pacotes na deteccao por volume (`observe` + `check_volume`) e,
    com um `sender` (src.alerts.AlertSender), manda os alertas para a API.
    """

    def __init__(self, source, db_path=storage.DB_PATH, volume_limits=None, sender=None):
        self.ids = IDSPipeline.load()
        self.features = model_features(self.ids)
        self.volume = VolumeDetector(volume_limits)
        self.sender = sender
        self.conn = storage.connect(db_path)
        self.run_id = storage.start_run(self.conn, source)
        self.counts = Counter()
        self.volume_counts = Counter()

    @property
    def total(self):
        return sum(self.counts.values())

    @property
    def attacks(self):
        return self.total - self.counts[BENIGN]

    def process(self, flows):
        """Classifica e grava uma lista de fluxos (dicts de src.flows).

        Devolve um DataFrame com as features e as colunas da previsao. Taxas com
        duracao zero (inf/NaN) vao para o modelo como valor ausente; o XGBoost
        trata ausentes nativamente, entao o fluxo nao e descartado.
        """
        if not flows:
            return None
        df = pd.DataFrame(flows)
        pred = self.ids.predict(df[self.features].replace([np.inf, -np.inf], np.nan))
        volume = pd.Series([self.volume.match(*key) for key in zip(
                                df['Src IP'], df['Dst IP'], df['Protocol'], df['Dst Port'], df['Timestamp'])],
                           index=pred.index, dtype=object)
        hit, model = volume.notna(), pred['is_attack'] == 1
        pred['model_type'] = pred['attack_type']
        pred['detected_by'] = pd.Series(None, index=pred.index, dtype=object)
        pred.loc[model, 'detected_by'] = 'modelo'
        pred.loc[hit, 'detected_by'] = np.where(model[hit], 'modelo+volume', 'volume')
        pred.loc[hit, 'attack_type'] = volume[hit]
        pred.loc[hit, 'is_attack'] = 1
        storage.save_flows(self.conn, self.run_id, df, pred, self.features)
        self.counts.update(pred['attack_type'])
        rows = df.join(pred)
        if self.sender:
            self.sender.send(model_alerts(rows))
        return rows

    def observe(self, pkt):
        self.volume.add(pkt)

    def check_volume(self, now_us):
        """Checa a janela de volume que termina em `now_us`; grava e devolve os alertas novos.

        Fluxos de um ataque ativo que ja tinham sido gravados (encerraram antes do
        alerta) sao reclassificados no banco.
        """
        alerts = self.volume.check(now_us)
        if alerts:
            storage.save_volume_alerts(self.conn, self.run_id, alerts)
            self.volume_counts.update(a['type'] for a in alerts)
            if self.sender:
                self.sender.send(volume_alerts(alerts))
        changed = 0
        for attack in self.volume.active.values():
            keep = VOLUME_TYPES[:VOLUME_TYPES.index(attack.type)]
            changed += storage.relabel_flows(self.conn, self.run_id, attack, PROTOCOL[attack.type], keep)
        if changed:
            self.counts = Counter(dict(self.conn.execute(
                'SELECT attack_type, COUNT(*) FROM flows WHERE run_id = ? GROUP BY 1', (self.run_id,))))
        return alerts

    def close(self):
        storage.finish_run(self.conn, self.run_id)
        self.conn.close()


def run(pcap, db_path=storage.DB_PATH, batch_size=5000, sender=None):
    """Analisa um arquivo PCAP inteiro; devolve o id da execucao no banco.

    O relogio e o dos pacotes: a janela de volume e checada a cada segundo da captura.
    """
    detector = Detector(pcap, db_path, sender=sender)
    meter = FlowMeter()
    inicio = time.perf_counter()
    batch = []
    second = None
    last_ts = 0
    for pkt in read_pcap(pcap):
        if pkt.ts // 1_000_000 != second:
            if second is not None:
                detector.check_volume(pkt.ts)
            second = pkt.ts // 1_000_000
        last_ts = pkt.ts
        detector.observe(pkt)
        batch += meter.process(pkt)
        if len(batch) >= batch_size:
            detector.process(batch)
            batch = []
            print(f'\r{detector.total:,} fluxos processados', end='', flush=True)
    detector.check_volume(last_ts)
    detector.process(batch + meter.flush())
    detector.close()
    print(f'\r{detector.total:,} fluxos processados em {time.perf_counter() - inicio:.1f}s')
    return detector.run_id
