-- Incidentes: varios alertas do mesmo ataque viram um incidente so.
-- Mesmo ataque = mesmo sensor + type + dst_ip, com no maximo 60 s entre um alerta e o seguinte
-- (regra em incident/IncidentService.java).
CREATE TABLE incidents (
    id            BIGSERIAL PRIMARY KEY,
    sensor        VARCHAR(100)     NOT NULL,
    type          VARCHAR(50)      NOT NULL,
    dst_ip        VARCHAR(45)      NOT NULL,
    started_at    TIMESTAMPTZ      NOT NULL,   -- ts do primeiro alerta
    last_seen_at  TIMESTAMPTZ      NOT NULL,   -- ts do ultimo alerta
    alert_count   INTEGER          NOT NULL,
    peak_rate     DOUBLE PRECISION             -- maior rate (pacotes/s); NULL se so vieram alertas do modelo
);

CREATE INDEX idx_incidents_chave ON incidents (sensor, type, dst_ip, last_seen_at);

-- Alertas antigos (de antes desta migracao) ficam sem incidente, por isso a coluna aceita NULL.
ALTER TABLE alerts ADD COLUMN incident_id BIGINT REFERENCES incidents (id);

CREATE INDEX idx_alerts_incident ON alerts (incident_id);
