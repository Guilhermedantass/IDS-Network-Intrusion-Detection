package dev.guilhermedantas.ids.sensor;

import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

/**
 * Os sensores conhecidos e o que foi pedido para cada um. Fica so na memoria: o estado de verdade esta
 * no sensor, e ele manda de novo a cada 5 s. Se a API reiniciar, o primeiro heartbeat recria tudo.
 *
 * ConcurrentHashMap porque os heartbeats (dos sensores) e os pedidos (do dashboard) chegam em threads
 * diferentes do servidor ao mesmo tempo.
 */
@Service
public class SensorRegistry {

    /** Sem heartbeat ha mais que isso (3 heartbeats perdidos), o sensor aparece como offline. */
    static final Duration OFFLINE_AFTER = Duration.ofSeconds(15);

    private record Entry(Instant lastSeen, SensorHeartbeat reported, SensorCommand desired) {
    }

    private final Map<String, Entry> sensors = new ConcurrentHashMap<>();

    /**
     * Guarda o estado e devolve o desejado. Sensor novo (ou API que acabou de reiniciar) adota o estado
     * atual como desejado: assim reiniciar a API nao para uma captura que estava rodando.
     */
    public SensorCommand heartbeat(SensorHeartbeat hb) {
        Entry entry = sensors.compute(hb.sensor(), (name, old) -> new Entry(
                Instant.now(),
                hb,
                old != null ? old.desired() : new SensorCommand(hb.capturing(), hb.iface())));
        return entry.desired();
    }

    public List<SensorView> list() {
        return list(Instant.now());
    }

    List<SensorView> list(Instant now) {
        return sensors.entrySet().stream()
                .map(e -> view(e.getKey(), e.getValue(), now))
                .sorted(Comparator.comparing(SensorView::name))
                .toList();
    }

    /** O dashboard pede: so vale para sensor conhecido, e a interface tem que existir nele. */
    public SensorView request(String name, SensorCommand command) {
        Entry entry = sensors.computeIfPresent(name, (n, old) -> {
            String iface = command.iface();
            if (iface != null && !old.reported().interfaces().contains(iface)) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "O sensor " + n + " nao tem a interface " + iface);
            }
            return new Entry(old.lastSeen(), old.reported(), command);
        });
        if (entry == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Sensor " + name + " nao conhecido");
        }
        return view(name, entry, Instant.now());
    }

    private static SensorView view(String name, Entry e, Instant now) {
        boolean online = Duration.between(e.lastSeen(), now).compareTo(OFFLINE_AFTER) <= 0;
        return new SensorView(name, online, e.lastSeen(), e.reported(), e.desired());
    }
}
