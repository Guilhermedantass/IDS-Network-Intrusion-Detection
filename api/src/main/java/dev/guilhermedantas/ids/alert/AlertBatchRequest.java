package dev.guilhermedantas.ids.alert;

/**
 * Corpo do POST /api/alerts que o sensor manda: {"sensor": "pc-casa", "alerts": [...]}.
 * Formato definido em sensor/src/alerts.py (e no README da raiz).
 *
 * TODO: adicionar os dois campos do JSON como componentes do record:
 *   - sensor: texto obrigatorio (validacao: @NotBlank)
 *   - alerts: lista de AlertRequest, obrigatoria e nao vazia (@NotEmpty)
 *     Dica: @Valid na lista faz o Spring validar cada AlertRequest de dentro tambem.
 */
public record AlertBatchRequest() {
}
