package dev.guilhermedantas.ids.alert;

/**
 * Um alerta do lote. Exemplo:
 * <pre>
 * {"ts": "2026-10-22T13:33:19Z", "type": "SYN Flood", "detectedBy": "volume",
 *  "srcIp": "127.0.0.1", "dstIp": "127.0.0.1", "dstPort": 9, "protocol": "TCP",
 *  "flows": null, "packets": 1800, "rate": 180.0, "ports": 1, "sources": null, "probability": null}
 * </pre>
 *
 * TODO: um componente para cada campo do JSON (mesmo nome, o Jackson casa pelo nome).
 *   - ts: java.time.Instant (o Jackson converte o texto ISO "...Z" sozinho)
 *   - campos que podem vir null (srcIp, dstPort, flows, packets, rate, ports, sources, probability):
 *     use tipos "caixa" (Integer, Double), porque int/double nao aceitam null
 *   - obrigatorios: ts (@NotNull), type, detectedBy, dstIp, protocol (@NotBlank)
 */
public record AlertRequest() {
}
