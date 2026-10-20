"""Carregamento e limpeza dos CSVs do CIC-IDS-2017.

As mesmas funcoes de limpeza sao usadas no treino e na deteccao ao vivo,
para garantir que os modelos recebam as features no mesmo formato.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

RAW_DIR = Path(__file__).resolve().parent.parent / 'datas' / 'raw'
RAW_FILES = ['DDos.csv', 'PortScan.csv', 'WebAttacks.csv']

BENIGN = 'BENIGN'

# Os labels de ataques web vem com um caractere quebrado no CSV original
# ('Web Attack � XSS'); aqui viram nomes simples.
# BruteForce e XSS viram uma classe so: as features de fluxo nao veem o conteudo
# das requisicoes HTTP, e os dois se confundem (~50% de erro entre eles).
LABEL_MAP = {
    'BENIGN': BENIGN,
    'DDoS': 'DDoS',
    'PortScan': 'PortScan',
    'Web Attack � Brute Force': 'WebAttack',
    'Web Attack � XSS': 'WebAttack',
    'Web Attack � Sql Injection': 'SQLInjection',
}

# Colunas constantes (sempre zero) no CIC-IDS-2017.
CONSTANT_COLUMNS = [
    'Bwd PSH Flags', 'Fwd URG Flags', 'Bwd URG Flags', 'CWE Flag Count',
    'Fwd Avg Bytes/Bulk', 'Fwd Avg Packets/Bulk', 'Fwd Avg Bulk Rate',
    'Bwd Avg Bytes/Bulk', 'Bwd Avg Packets/Bulk', 'Bwd Avg Bulk Rate',
]

# Colunas identicas a outra coluna que e mantida (mantida -> removida).
DUPLICATE_COLUMNS = {
    'Total Fwd Packets': 'Subflow Fwd Packets',
    'Total Backward Packets': 'Subflow Bwd Packets',
    'Total Length of Fwd Packets': 'Subflow Fwd Bytes',
    'Fwd Packet Length Mean': 'Avg Fwd Segment Size',
    'Fwd PSH Flags': 'SYN Flag Count',
    'Fwd Header Length': 'Fwd Header Length.1',
    'RST Flag Count': 'ECE Flag Count',
}

# Features que funcionam como "atalho": identificam o ataque pelo ambiente da
# captura e nao pelo comportamento do trafego.
# - Destination Port: cada ataque mira portas especificas.
# - Init_Win_bytes_*: janela TCP inicial depende do SO de quem envia (29200 =
#   Linux do atacante Kali, 8192 = Windows do DDoS); identifica a maquina, nao o ataque.
SHORTCUT_COLUMNS = ['Destination Port', 'Init_Win_bytes_forward', 'Init_Win_bytes_backward']

# Colunas de flags TCP: o CICFlowMeter que gerou o dataset as calcula errado
# (ex.: fluxos de port scan so tem 'PSH', nunca o RST das portas fechadas; ACK
# aparece em so 14% das conexoes longas). Um extrator correto nunca reproduz
# esses valores, entao elas ficam fora dos modelos.
FLAG_COLUMNS = [
    'FIN Flag Count', 'SYN Flag Count', 'RST Flag Count', 'PSH Flag Count',
    'ACK Flag Count', 'URG Flag Count', 'CWE Flag Count', 'ECE Flag Count',
    'Fwd PSH Flags', 'Bwd PSH Flags', 'Fwd URG Flags', 'Bwd URG Flags',
]

DROP_COLUMNS = list(dict.fromkeys(
    CONSTANT_COLUMNS + list(DUPLICATE_COLUMNS.values()) + SHORTCUT_COLUMNS + FLAG_COLUMNS))


def load_raw(files=RAW_FILES, raw_dir=RAW_DIR):
    """Le e concatena os CSVs, com nomes de colunas e labels padronizados."""
    frames = []
    for name in files:
        df = pd.read_csv(Path(raw_dir) / name)
        df.columns = df.columns.str.strip()
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df['Label'] = df['Label'].str.strip().map(LABEL_MAP)
    if df['Label'].isna().any():
        raise ValueError('Label desconhecido nos CSVs; atualize LABEL_MAP')
    return df


def clean_features(df):
    """Limpeza aplicada tanto no treino quanto na deteccao ao vivo."""
    df = df.drop(columns=DROP_COLUMNS, errors='ignore')
    df = df.replace([np.inf, -np.inf], np.nan)
    return df.dropna()


def build_dataset(files=RAW_FILES, raw_dir=RAW_DIR):
    """Dataset limpo e sem duplicatas, com as colunas de alvo dos dois modelos.

    - is_attack: alvo do modelo binario (0 = BENIGN, 1 = ataque)
    - attack_type: alvo do modelo de tipo de ataque (o proprio Label)
    """
    df = clean_features(load_raw(files, raw_dir))
    df = df.drop_duplicates()

    # Linhas com as mesmas features e labels diferentes nao tem rotulo confiavel.
    features = df.columns.drop('Label')
    df = df[~df.duplicated(subset=features, keep=False)]

    df = df.rename(columns={'Label': 'attack_type'})
    df['is_attack'] = (df['attack_type'] != BENIGN).astype(int)
    return df.reset_index(drop=True)


def split_xy(df):
    """Separa features e alvos."""
    X = df.drop(columns=['attack_type', 'is_attack'])
    return X, df['is_attack'], df['attack_type']


def train_test(df, test_size=0.2, random_state=42):
    """Divisao unica usada pelos dois modelos.

    Estratificada pelo tipo de ataque, para que as classes raras (SQLInjection)
    aparecam no treino e no teste. O teste mantem a distribuicao original e
    nunca e balanceado.
    """
    return train_test_split(df, test_size=test_size, stratify=df['attack_type'],
                            random_state=random_state)
