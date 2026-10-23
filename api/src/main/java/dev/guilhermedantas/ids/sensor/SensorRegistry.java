package dev.guilhermedantas.ids.sensor;

import java.net.InetAddress;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Function;

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
     * atual como desejado: assim reiniciar a API nao para uma captura nem desfaz um bloqueio.
     */
    public SensorCommand heartbeat(SensorHeartbeat hb) {
        Entry entry = sensors.compute(hb.sensor(), (name, old) -> new Entry(
                Instant.now(),
                hb,
                old != null ? old.desired()
                        : new SensorCommand(hb.capturing(), hb.iface(), Objects.requireNonNullElse(hb.blocked(), List.of()))));
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

    /** O dashboard pede iniciar/parar: a interface tem que existir no sensor. */
    public SensorView request(String name, CaptureRequest request) {
        return update(name, old -> {
            String iface = request.iface();
            if (iface != null && !old.reported().interfaces().contains(iface)) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "O sensor " + name + " nao tem a interface " + iface);
            }
            return old.desired().withCapture(request);
        });
    }

    /**
     * O dashboard pede para bloquear um IP. Recusa o que nao e IP e os protegidos (loopback e os que o
     * sensor diz que sao dele, do gateway ou da API). O sensor confere de novo: e ele que roda o firewall.
     */
    public SensorView block(String name, String ip) {
        InetAddress addr = parseIp(ip);
        return update(name, old -> {
            if (isProtected(addr, old.reported())) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        ip + " e protegido no sensor " + name + " (proprio PC, gateway ou API)");
            }
            List<String> blocked = new ArrayList<>(old.desired().blocked());
            if (!blocked.contains(ip)) {
                blocked.add(ip);
            }
            return old.desired().withBlocked(blocked);
        });
    }

    public SensorView unblock(String name, String ip) {
        return update(name, old -> old.desired().withBlocked(
                old.desired().blocked().stream().filter(b -> !b.equals(ip)).toList()));
    }

    /** Troca o desejado de um sensor conhecido (404 se nao for). */
    private SensorView update(String name, Function<Entry, SensorCommand> desired) {
        Entry entry = sensors.computeIfPresent(name,
                (n, old) -> new Entry(old.lastSeen(), old.reported(), desired.apply(old)));
        if (entry == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Sensor " + name + " nao conhecido");
        }
        return view(name, entry, Instant.now());
    }

    /** InetAddress.ofLiteral so aceita IP escrito (nunca faz consulta DNS, como o getByName faria). */
    private static InetAddress parseIp(String ip) {
        try {
            return InetAddress.ofLiteral(ip);
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, ip + " nao e um IP");
        }
    }

    private static boolean isProtected(InetAddress addr, SensorHeartbeat reported) {
        if (addr.isLoopbackAddress() || addr.isAnyLocalAddress() || addr.isMulticastAddress()) {
            return true;
        }
        // compara como InetAddress: "2001:db8::7" e "2001:db8:0:0:0:0:0:7" sao o mesmo IP
        List<String> protectedIps = Objects.requireNonNullElse(reported.protectedIps(), List.of());
        return protectedIps.stream().anyMatch(p -> {
            try {
                return InetAddress.ofLiteral(p).equals(addr);
            } catch (IllegalArgumentException e) {
                return false;
            }
        });
    }

    private static SensorView view(String name, Entry e, Instant now) {
        boolean online = Duration.between(e.lastSeen(), now).compareTo(OFFLINE_AFTER) <= 0;
        return new SensorView(name, online, e.lastSeen(), e.reported(), e.desired());
    }
}
