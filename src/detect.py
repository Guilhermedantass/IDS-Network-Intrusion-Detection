"""Classificacao de fluxos e gravacao no SQLite, usada pelo modo arquivo e pelo ao vivo."""
import time
from collections import Counter

import numpy as np
import pandas as pd

from . import storage
from .flows import flows_from_pcap
from .pipeline import IDSPipeline


def model_features(ids):
    return list(dict.fromkeys(ids.binary_meta['features'] + ids.attack_meta['features']))


class Detector:
    """Classifica lotes de fluxos com o IDSPipeline e grava tudo em uma execucao (run) do banco."""

    def __init__(self, source, db_path=storage.DB_PATH):
        self.ids = IDSPipeline.load()
        self.features = model_features(self.ids)
        self.conn = storage.connect(db_path)
        self.run_id = storage.start_run(self.conn, source)
        self.counts = Counter()

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

    def close(self):
        storage.finish_run(self.conn, self.run_id)
        self.conn.close()


def run(pcap, db_path=storage.DB_PATH, batch_size=5000):
    """Analisa um arquivo PCAP inteiro; devolve o id da execucao no banco."""
    detector = Detector(pcap, db_path)
    inicio = time.perf_counter()
    batch = []
    for flow in flows_from_pcap(pcap):
        batch.append(flow)
        if len(batch) >= batch_size:
            detector.process(batch)
            batch = []
            print(f'\r{detector.total:,} fluxos processados', end='', flush=True)
    detector.process(batch)
    detector.close()
    print(f'\r{detector.total:,} fluxos processados em {time.perf_counter() - inicio:.1f}s')
    return detector.run_id
