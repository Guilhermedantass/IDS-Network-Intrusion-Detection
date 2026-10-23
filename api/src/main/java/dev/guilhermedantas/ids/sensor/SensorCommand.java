package dev.guilhermedantas.ids.sensor;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * O estado desejado de um sensor, a resposta do heartbeat (o sensor obedece): capturar ou nao, em qual
 * interface (null = a padrao do sensor) e quais IPs bloquear no firewall dele.
 */
public record SensorCommand(boolean capture, @JsonProperty("interface") String iface, List<String> blocked) {

    SensorCommand withCapture(CaptureRequest request) {
        return new SensorCommand(request.capture(), request.iface(), blocked);
    }

    SensorCommand withBlocked(List<String> blocked) {
        return new SensorCommand(capture, iface, List.copyOf(blocked));
    }
}
