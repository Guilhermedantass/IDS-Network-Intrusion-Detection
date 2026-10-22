"""Classificacao de fluxos e gravacao no SQLite, usada pelo modo arquivo e pelo ao vivo."""
import time
from collections import Counter

import numpy as np
import pandas as pd

from . import storage
from .flows import FlowMeter, read_pcap
from .pipeline import IDSPipeline
from .volume import VolumeDetector


def model_features(ids):
    return list(dict.fromkeys(ids.binary_meta['features'] + ids.attack_meta['features']))


class Detector:
    """Classifica lotes de fluxos com o IDSPipeline e grava tudo em uma execucao (run) do banco.

    Tambem soma os pacotes na deteccao por volume (`observe` + `check_volume`).
    """

    def __init__(self, source, db_path=storage.DB_PATH, volume_limits=None):
        self.ids = IDSPipeline.load()
        self.features = model_features(self.ids)
        self.volume = VolumeDetector(volume_limits)
        self.conn = storage.connect(db_path)
        self.run_id = storage.start_run(self.conn, source)
        self.counts = Counter()
        self.volume_counts = Counter()

    @property
    def total(self):
        return sum(self.counts.values())

    @property
    def attacks(self):
        return self.total - self.counts['BENIGN']

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
        storage.save_flows(self.conn, self.run_id, df, pred, self.features)
        self.counts.update(pred['attack_type'])
        return df.join(pred)

    def observe(self, pkt):
        self.volume.add(pkt)

    def check_volume(self, now_us):
        """Checa a janela de volume que termina em `now_us`; grava e devolve os alertas."""
        alerts = self.volume.check(now_us)
        if alerts:
            storage.save_volume_alerts(self.conn, self.run_id, alerts)
            self.volume_counts.update(a['type'] for a in alerts)
        return alerts

    def close(self):
        storage.finish_run(self.conn, self.run_id)
        self.conn.close()


def run(pcap, db_path=storage.DB_PATH, batch_size=5000):
    """Analisa um arquivo PCAP inteiro; devolve o id da execucao no banco.

    O relogio e o dos pacotes: a janela de volume e checada a cada segundo da captura.
    """
    detector = Detector(pcap, db_path)
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
