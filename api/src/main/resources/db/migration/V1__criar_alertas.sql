-- Alertas recebidos do sensor (POST /api/alerts). Uma linha por alerta do lote.
-- Campos seguem o contrato de sensor/src/alerts.py; os que nao se aplicam ficam NULL.
CREATE TABLE alerts (
    id           BIGSERIAL PRIMARY KEY,
    sensor       VARCHAR(100)     NOT NULL,   -- nome do sensor que mandou
    ts           TIMESTAMPTZ      NOT NULL,   -- quando o ataque foi visto (relogio do sensor)
    received_at  TIMESTAMPTZ      NOT NULL DEFAULT now(),
    type         VARCHAR(50)      NOT NULL,   -- SYN Flood, PortScan, DDoS, WebAttack...
    detected_by  VARCHAR(20)      NOT NULL,   -- modelo ou volume
    src_ip       VARCHAR(45),                 -- NULL no DDoS (muitas origens); 45 cabe IPv6
    dst_ip       VARCHAR(45)      NOT NULL,
    dst_port     INTEGER,
    protocol     VARCHAR(10)      NOT NULL,   -- TCP ou UDP
    flows        INTEGER,                     -- so modelo
    packets      INTEGER,                     -- so volume
    rate         DOUBLE PRECISION,            -- so volume, pacotes/s
    ports        INTEGER,
    sources      INTEGER,                     -- so DDoS
    probability  DOUBLE PRECISION             -- so modelo
);

CREATE INDEX idx_alerts_ts ON alerts (ts);
CREATE INDEX idx_alerts_dst ON alerts (dst_ip, type);
