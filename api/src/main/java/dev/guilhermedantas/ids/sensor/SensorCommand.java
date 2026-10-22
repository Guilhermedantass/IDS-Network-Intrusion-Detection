package dev.guilhermedantas.ids.sensor;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * O estado desejado de um sensor: capturar ou nao, e em qual interface (null = a padrao do sensor).
 * E a resposta do heartbeat (o sensor obedece) e o corpo do PUT /api/sensors/{name}/capture (o dashboard pede).
 */
public record SensorCommand(boolean capture, @JsonProperty("interface") String iface) {
}
