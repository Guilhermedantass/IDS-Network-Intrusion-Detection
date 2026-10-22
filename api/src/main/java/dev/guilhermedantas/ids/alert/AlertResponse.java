package dev.guilhermedantas.ids.alert;

import java.time.Instant;

/**
 * Um alerta como o dashboard recebe em GET /api/alerts?incident=ID. Mesmos campos que o sensor manda
 * (AlertRequest), mais o id e o receivedAt (quando a API recebeu). O sensor fica no incidente.
 */
public record AlertResponse(
        Long id,
        Instant ts,
        Instant receivedAt,
        String type,
        String detectedBy,
        String srcIp,
        String dstIp,
        Integer dstPort,
        String protocol,
        Integer flows,
        Integer packets,
        Double rate,
        Integer ports,
        Integer sources,
        Double probability) {
}
