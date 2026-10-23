package dev.guilhermedantas.ids.sensor;

import java.time.Instant;

/**
 * Um sensor como o dashboard ve (GET /api/sensors): o ultimo estado que ele mandou, se ainda esta
 * online (mandou heartbeat ha pouco) e o que foi pedido para ele. Pedido diferente do estado = o sensor
 * ainda vai aplicar (no proximo heartbeat).
 */
public record SensorView(String name, boolean online, Instant lastSeen, SensorHeartbeat reported, SensorCommand desired) {
}
