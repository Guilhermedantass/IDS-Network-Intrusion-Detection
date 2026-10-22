package dev.guilhermedantas.ids.incident;

import java.time.Instant;

/**
 * O que o dashboard recebe em /topic/incidents. Sempre o estado completo do incidente:
 * o dashboard troca pelo id (se ja tem, atualiza; se nao, e um incidente novo).
 */
public record IncidentMessage(
        Long id,
        String sensor,
        String type,
        String dstIp,
        Instant startedAt,
        Instant lastSeenAt,
        int alertCount,
        Double peakRate) {

    static IncidentMessage from(Incident i) {
        return new IncidentMessage(i.getId(), i.getSensor(), i.getType(), i.getDstIp(),
                i.getStartedAt(), i.getLastSeenAt(), i.getAlertCount(), i.getPeakRate());
    }
}
