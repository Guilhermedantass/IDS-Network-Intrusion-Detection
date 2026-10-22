"""Armazenamento das deteccoes em SQLite (lido pelo dashboard)."""
import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / 'results' / 'ids.db'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,           -- arquivo PCAP ou interface de rede
    started_at  REAL NOT NULL,
    finished_at REAL,
    flows       INTEGER DEFAULT 0,
    attacks     INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS flows (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES runs(id),
    ts              REAL NOT NULL,       -- inicio do fluxo (epoch, segundos)
    duration_us     INTEGER NOT NULL,
    src_ip          TEXT, src_port INTEGER,
    dst_ip          TEXT, dst_port INTEGER,
    protocol        INTEGER,
    fwd_packets     INTEGER, bwd_packets INTEGER,
    fwd_bytes       INTEGER, bwd_bytes   INTEGER,
    attack_prob     REAL NOT NULL,
    is_attack       INTEGER NOT NULL,
    attack_type     TEXT NOT NULL,
    type_confidence REAL,
    features        TEXT                 -- JSON com as features, so para ataques
);

CREATE INDEX IF NOT EXISTS idx_flows_ts ON flows(ts);
CREATE INDEX IF NOT EXISTS idx_flows_attack ON flows(is_attack, attack_type);

-- alertas da deteccao por volume (src.volume): trafego somado, nao um fluxo
CREATE TABLE IF NOT EXISTS volume_alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    ts          REAL NOT NULL,           -- fim da janela (epoch, segundos)
    type        TEXT NOT NULL,           -- SYN Flood, DDoS, UDP Flood, PortScan
    src_ip      TEXT,                    -- NULL no DDoS (muitas origens)
    dst_ip      TEXT NOT NULL,
    packets     INTEGER NOT NULL,        -- pacotes contados na janela
    rate        REAL NOT NULL,           -- pacotes/s na janela
    ports       INTEGER,
    sources     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_volume_run ON volume_alerts(run_id, ts);
'''


def connect(db_path=DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def start_run(conn, source):
    cur = conn.execute('INSERT INTO runs (source, started_at) VALUES (?, ?)', (str(source), time.time()))
    conn.commit()
    return cur.lastrowid


def finish_run(conn, run_id):
    conn.execute('''
        UPDATE runs SET finished_at = ?,
            flows   = (SELECT COUNT(*) FROM flows WHERE run_id = ?),
            attacks = (SELECT COUNT(*) FROM flows WHERE run_id = ? AND is_attack = 1)
        WHERE id = ?''', (time.time(), run_id, run_id, run_id))
    conn.commit()


def _clean(value):
    """JSON nao aceita inf/NaN; viram null."""
    return None if isinstance(value, float) and (value != value or value in (float('inf'), float('-inf'))) else value


def save_flows(conn, run_id, flows, predictions, feature_columns):
    """Salva um lote de fluxos (DataFrame de src.flows) com as previsoes do IDSPipeline."""
    rows = []
    for (_, f), (_, p) in zip(flows.iterrows(), predictions.iterrows()):
        features = None
        if p['is_attack']:
            features = json.dumps({c: _clean(f[c]) for c in feature_columns})
        rows.append((
            run_id, f['Timestamp'], int(f['Flow Duration']),
            f['Src IP'], int(f['Src Port']), f['Dst IP'], int(f['Dst Port']), int(f['Protocol']),
            int(f['Total Fwd Packets']), int(f['Total Backward Packets']),
            int(f['Total Length of Fwd Packets']), int(f['Total Length of Bwd Packets']),
            float(p['attack_prob']), int(p['is_attack']), p['attack_type'],
            None if p['type_confidence'] != p['type_confidence'] else float(p['type_confidence']),
            features,
        ))
    conn.executemany('''
        INSERT INTO flows (run_id, ts, duration_us, src_ip, src_port, dst_ip, dst_port, protocol,
                           fwd_packets, bwd_packets, fwd_bytes, bwd_bytes,
                           attack_prob, is_attack, attack_type, type_confidence, features)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', rows)
    conn.commit()


def save_volume_alerts(conn, run_id, alerts):
    """Salva os alertas de src.volume (lista de dicts)."""
    conn.executemany('''
        INSERT INTO volume_alerts (run_id, ts, type, src_ip, dst_ip, packets, rate, ports, sources)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        [(run_id, a['ts'], a['type'], a['src_ip'], a['dst_ip'], a['packets'], a['rate'],
          a['ports'], a['sources']) for a in alerts])
    conn.commit()
