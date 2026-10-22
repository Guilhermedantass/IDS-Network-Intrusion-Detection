"""Deteccao em duas etapas: (1) e ataque? (2) qual ataque?"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from .data import BENIGN

MODELS_DIR = Path(__file__).resolve().parent.parent / 'results' / 'modelos'
UNKNOWN = 'Desconhecido'


def save_model(model, name, metadata, models_dir=MODELS_DIR):
    """Salva o modelo XGBoost (.ubj) e os metadados (features, limiar, classes)."""
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    model.save_model(models_dir / f'{name}.ubj')
    with open(models_dir / f'{name}.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def load_model(name, models_dir=MODELS_DIR):
    models_dir = Path(models_dir)
    with open(models_dir / f'{name}.json', encoding='utf-8') as f:
        metadata = json.load(f)
    model = xgb.XGBClassifier()
    model.load_model(models_dir / f'{name}.ubj')
    return model, metadata


class IDSPipeline:
    """Modelo binario (BENIGN x ataque) seguido do modelo de tipo de ataque.

    Fluxos com probabilidade de ataque >= limiar do binario seguem para o
    modelo de tipo. Se a confianca do tipo ficar abaixo do limiar dele, o
    ataque e marcado como 'Desconhecido'.
    """

    def __init__(self, binary, binary_meta, attack, attack_meta):
        self.binary, self.binary_meta = binary, binary_meta
        self.attack, self.attack_meta = attack, attack_meta

    @classmethod
    def load(cls, models_dir=MODELS_DIR):
        return cls(*load_model('modelo_binario', models_dir),
                   *load_model('modelo_tipo_ataque', models_dir))

    def predict(self, X):
        """Recebe features limpas (src.data.clean_features) e devolve um DataFrame com:
        attack_prob, is_attack, attack_type e type_confidence."""
        attack_prob = self.binary.predict_proba(X[self.binary_meta['features']])[:, 1]
        is_attack = attack_prob >= self.binary_meta['threshold']

        out = pd.DataFrame({'attack_prob': attack_prob, 'is_attack': is_attack.astype(int),
                            'attack_type': BENIGN, 'type_confidence': np.nan}, index=X.index)
        if is_attack.any():
            proba = self.attack.predict_proba(X.loc[is_attack, self.attack_meta['features']])
            classes = np.array(self.attack_meta['classes'])
            confidence = proba.max(axis=1)
            types = np.where(confidence >= self.attack_meta['threshold'],
                             classes[proba.argmax(axis=1)], UNKNOWN)
            out.loc[is_attack, 'attack_type'] = types
            out.loc[is_attack, 'type_confidence'] = confidence
        return out
