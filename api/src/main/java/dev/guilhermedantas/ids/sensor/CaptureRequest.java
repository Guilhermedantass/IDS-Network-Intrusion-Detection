package dev.guilhermedantas.ids.sensor;

import com.fasterxml.jackson.annotation.JsonProperty;

/** O corpo do PUT /api/sensors/{name}/capture: iniciar/parar a captura. interface null = a padrao do sensor. */
public record CaptureRequest(boolean capture, @JsonProperty("interface") String iface) {
}
