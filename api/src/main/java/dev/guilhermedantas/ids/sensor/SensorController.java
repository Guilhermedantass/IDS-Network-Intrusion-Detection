package dev.guilhermedantas.ids.sensor;

import java.util.List;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;

/**
 * Controle dos sensores. O sensor nunca recebe chamadas: ele manda o heartbeat e recebe na resposta o que
 * deve fazer. O dashboard so le a lista e muda o desejado.
 *
 *   POST /api/sensors/heartbeat         (sensor)    estado atual -> estado desejado
 *   GET  /api/sensors                   (dashboard) os sensores conhecidos
 *   PUT    /api/sensors/{name}/capture       (dashboard) {"capture": true, "interface": "lo"}
 *   PUT    /api/sensors/{name}/blocked/{ip}  (dashboard) bloquear o IP no firewall do sensor
 *   DELETE /api/sensors/{name}/blocked/{ip}  (dashboard) desbloquear
 */
@RestController
@RequestMapping("/api/sensors")
public class SensorController {

    private final SensorRegistry registry;

    public SensorController(SensorRegistry registry) {
        this.registry = registry;
    }

    @PostMapping("/heartbeat")
    public SensorCommand heartbeat(@Valid @RequestBody SensorHeartbeat heartbeat) {
        return registry.heartbeat(heartbeat);
    }

    @GetMapping
    public List<SensorView> list() {
        return registry.list();
    }

    @PutMapping("/{name}/capture")
    public SensorView request(@PathVariable String name, @RequestBody CaptureRequest request) {
        return registry.request(name, request);
    }

    @PutMapping("/{name}/blocked/{ip}")
    public SensorView block(@PathVariable String name, @PathVariable String ip) {
        return registry.block(name, ip);
    }

    @DeleteMapping("/{name}/blocked/{ip}")
    public SensorView unblock(@PathVariable String name, @PathVariable String ip) {
        return registry.unblock(name, ip);
    }
}
