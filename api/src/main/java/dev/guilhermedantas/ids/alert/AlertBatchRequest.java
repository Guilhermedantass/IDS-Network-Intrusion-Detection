package dev.guilhermedantas.ids.alert;

import java.util.List;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;

/**
 * Corpo do POST /api/alerts que o sensor manda: {"sensor": "pc-casa", "alerts": [...]}.
 * Formato definido em sensor/src/alerts.py (e no README da raiz).
 *
 * O @Valid na lista faz o Spring validar cada AlertRequest de dentro tambem.
 */
public record AlertBatchRequest(
        @NotBlank String sensor,
        @NotEmpty List<@Valid AlertRequest> alerts) {
}
