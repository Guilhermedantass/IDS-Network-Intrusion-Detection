package dev.guilhermedantas.ids.alert;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;

/**
 * Endpoint que o sensor chama: POST /api/alerts.
 *
 * Responde 201 Created (o sensor aceita qualquer 2xx). JSON invalido ou campo obrigatorio faltando:
 * o Spring ja responde 400 sozinho por causa do @Valid, e o sensor descarta o lote (4xx nao e reenviado).
 *
 * Testar sem o sensor:
 *   curl -i -X POST localhost:8080/api/alerts -H 'Content-Type: application/json' \
 *     -d '{"sensor":"teste","alerts":[{"ts":"2026-10-22T13:33:19Z","type":"SYN Flood",
 *          "detectedBy":"volume","dstIp":"127.0.0.1","protocol":"TCP"}]}'
 */
@RestController
@RequestMapping("/api/alerts")
public class AlertController {

    private final AlertService service;

    public AlertController(AlertService service) {
        this.service = service;
    }

    record SaveResponse(int saved) {
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public SaveResponse receive(@Valid @RequestBody AlertBatchRequest batch) {
        return new SaveResponse(service.save(batch));
    }
}
