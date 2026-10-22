package dev.guilhermedantas.ids.alert;

/**
 * Endpoint que o sensor chama: POST /api/alerts.
 *
 * TODO:
 *   - anotar com @RestController e @RequestMapping("/api/alerts")
 *   - receber o AlertService pelo construtor
 *   - metodo com @PostMapping recebendo "@Valid @RequestBody AlertBatchRequest batch"
 *   - responder 201 Created (@ResponseStatus(HttpStatus.CREATED)); o sensor aceita qualquer 2xx
 *   - JSON invalido ou campo obrigatorio faltando: o Spring ja responde 400 sozinho por causa do @Valid,
 *     e o sensor descarta o lote (4xx nao e reenviado)
 *
 * Testar sem o sensor:
 *   curl -i -X POST localhost:8080/api/alerts -H 'Content-Type: application/json' \
 *     -d '{"sensor":"teste","alerts":[{"ts":"2026-10-22T13:33:19Z","type":"SYN Flood",
 *          "detectedBy":"volume","dstIp":"127.0.0.1","protocol":"TCP"}]}'
 */
public class AlertController {
}
