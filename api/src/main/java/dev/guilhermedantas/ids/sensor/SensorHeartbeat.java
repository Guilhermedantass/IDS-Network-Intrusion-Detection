package dev.guilhermedantas.ids.sensor;

import java.time.Instant;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/**
 * O "estou vivo" que o servico do sensor manda a cada 5 s (POST /api/sensors/heartbeat).
 * Formato definido em sensor/src/service.py.
 *
 * @param capturing  se esta capturando agora
 * @param iface      a interface da captura (null se parado). No JSON e "interface": em Java essa palavra
 *                   e reservada, entao o campo tem outro nome e o @JsonProperty liga os dois
 * @param startedAt  quando a captura comecou (null se parado)
 * @param flows      fluxos da captura atual (ou da ultima)
 * @param interfaces as interfaces de rede da maquina, para o dashboard oferecer
 * @param error      erro da ultima captura (ex.: tcpdump sem permissao), ou null
 */
public record SensorHeartbeat(
        @NotBlank String sensor,
        boolean capturing,
        @JsonProperty("interface") String iface,
        Instant startedAt,
        long flows,
        long attacks,
        long alertsSent,
        @NotNull List<String> interfaces,
        String error) {
}
