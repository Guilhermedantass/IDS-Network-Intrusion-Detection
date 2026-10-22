package dev.guilhermedantas.ids.alert;

import java.time.Instant;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/**
 * Um alerta do lote. Exemplo:
 * <pre>
 * {"ts": "2026-10-22T13:33:19Z", "type": "SYN Flood", "detectedBy": "volume",
 *  "srcIp": "127.0.0.1", "dstIp": "127.0.0.1", "dstPort": 9, "protocol": "TCP",
 *  "flows": null, "packets": 1800, "rate": 180.0, "ports": 1, "sources": null, "probability": null}
 * </pre>
 *
 * Os nomes dos componentes sao os mesmos do JSON: o Jackson casa pelo nome.
 * Campos que podem vir null usam tipos "caixa" (Integer, Double), porque int/double nao aceitam null.
 */
public record AlertRequest(
        @NotNull Instant ts,
        @NotBlank String type,
        @NotBlank String detectedBy,
        String srcIp,
        @NotBlank String dstIp,
        Integer dstPort,
        @NotBlank String protocol,
        Integer flows,
        Integer packets,
        Double rate,
        Integer ports,
        Integer sources,
        Double probability) {
}
