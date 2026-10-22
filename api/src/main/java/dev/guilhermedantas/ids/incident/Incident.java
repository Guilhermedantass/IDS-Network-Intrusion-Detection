package dev.guilhermedantas.ids.incident;

import java.time.Instant;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * Entidade JPA da tabela "incidents" (db/migration/V2__criar_incidentes.sql).
 * Um incidente junta os alertas de um mesmo ataque: mesmo sensor + type + dstIp, sem pausa longa entre eles.
 */
@Entity
@Table(name = "incidents")
public class Incident {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String sensor;
    private String type;
    private String dstIp;
    private Instant startedAt;
    private Instant lastSeenAt;
    private int alertCount;
    private Double peakRate;

    protected Incident() {   // exigido pelo JPA
    }

    /** Abre um incidente a partir do primeiro alerta. */
    Incident(String sensor, String type, String dstIp, Instant ts, Double rate) {
        this.sensor = sensor;
        this.type = type;
        this.dstIp = dstIp;
        this.startedAt = ts;
        this.lastSeenAt = ts;
        this.alertCount = 1;
        this.peakRate = rate;
    }

    /** Junta mais um alerta: estende o intervalo, conta e guarda o pico. */
    void addAlert(Instant ts, Double rate) {
        if (ts.isBefore(startedAt)) {
            startedAt = ts;
        }
        if (ts.isAfter(lastSeenAt)) {
            lastSeenAt = ts;
        }
        alertCount++;
        if (rate != null && (peakRate == null || rate > peakRate)) {
            peakRate = rate;
        }
    }

    public Long getId() {
        return id;
    }

    public String getSensor() {
        return sensor;
    }

    public String getType() {
        return type;
    }

    public String getDstIp() {
        return dstIp;
    }

    public Instant getStartedAt() {
        return startedAt;
    }

    public Instant getLastSeenAt() {
        return lastSeenAt;
    }

    public int getAlertCount() {
        return alertCount;
    }

    public Double getPeakRate() {
        return peakRate;
    }
}
