package dev.guilhermedantas.ids.stats;

import static java.time.temporal.ChronoUnit.HOURS;
import static java.util.stream.Collectors.counting;
import static java.util.stream.Collectors.groupingBy;
import static java.util.stream.Collectors.toList;

import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Function;
import java.util.stream.IntStream;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import dev.guilhermedantas.ids.alert.Alert;
import dev.guilhermedantas.ids.alert.AlertRepository;
import dev.guilhermedantas.ids.incident.Incident;
import dev.guilhermedantas.ids.incident.IncidentRepository;
import dev.guilhermedantas.ids.stats.StatsResponse.Highlight;
import dev.guilhermedantas.ids.stats.StatsResponse.HourCount;
import dev.guilhermedantas.ids.stats.StatsResponse.IpCount;
import dev.guilhermedantas.ids.stats.StatsResponse.TypeCount;

/**
 * Contas da visao geral. A janela e de horas cheias: com hours = 24, vai do comeco da hora de 23 horas
 * atras ate agora (a hora atual conta, mesmo pela metade). O agrupamento e feito aqui no Java: sao
 * poucos incidentes por dia, entao nao vale escrever SQL de agrupamento.
 */
@Service
public class StatsService {

    static final int TOP = 5;

    private final IncidentRepository incidents;
    private final AlertRepository alerts;

    public StatsService(IncidentRepository incidents, AlertRepository alerts) {
        this.incidents = incidents;
        this.alerts = alerts;
    }

    @Transactional(readOnly = true)
    public StatsResponse summary(int hours) {
        Instant since = Instant.now().truncatedTo(HOURS).minus(hours - 1, HOURS);
        List<Incident> recent = incidents.findByStartedAtGreaterThanEqual(since);
        List<Alert> recentAlerts = alerts.findByTsGreaterThanEqual(since);

        List<TypeCount> byType = countBy(recent, Incident::getType).entrySet().stream()
                .map(e -> new TypeCount(e.getKey(), e.getValue()))
                .sorted(Comparator.comparingLong(TypeCount::incidents).reversed())
                .toList();

        // hora -> incidentes daquela hora; cada hora vira o total e a contagem por tipo
        Map<Instant, List<Incident>> perHour = recent.stream()
                .collect(groupingBy(i -> i.getStartedAt().truncatedTo(HOURS), toList()));
        List<HourCount> byHour = IntStream.range(0, hours)
                .mapToObj(k -> since.plus(k, HOURS))
                .map(hour -> {
                    List<Incident> inHour = perHour.getOrDefault(hour, List.of());   // hora sem incidente = 0
                    return new HourCount(hour, inHour.size(), countBy(inHour, Incident::getType));
                })
                .toList();

        Highlight highestRate = recent.stream()
                .filter(i -> i.getPeakRate() != null)
                .max(Comparator.comparingDouble(Incident::getPeakRate))
                .map(i -> new Highlight(i.getId(), i.getType(), i.getPeakRate()))
                .orElse(null);
        Highlight longest = recent.stream()
                .max(Comparator.comparing(StatsService::duration))
                .map(i -> new Highlight(i.getId(), i.getType(), duration(i).toSeconds()))
                .orElse(null);

        return new StatsResponse(since, recent.size(), recentAlerts.size(), highestRate, longest, byType, byHour,
                top(recentAlerts, Alert::getSrcIp), top(recentAlerts, Alert::getDstIp));
    }

    private static Duration duration(Incident i) {
        return Duration.between(i.getStartedAt(), i.getLastSeenAt());
    }

    private static <T> Map<String, Long> countBy(List<T> items, Function<T, String> key) {
        return items.stream().collect(groupingBy(key, counting()));
    }

    /** Os IPs com mais alertas (ignora alertas sem o IP), com quantos incidentes diferentes eles tiveram. */
    private static List<IpCount> top(List<Alert> alerts, Function<Alert, String> ip) {
        return alerts.stream()
                .filter(a -> ip.apply(a) != null)
                .collect(groupingBy(ip, toList()))
                .entrySet().stream()
                .map(e -> new IpCount(
                        e.getKey(),
                        e.getValue().stream().map(Alert::getIncidentId).filter(Objects::nonNull).distinct().count(),
                        e.getValue().size()))
                .sorted(Comparator.comparingLong(IpCount::alerts).reversed().thenComparing(IpCount::ip))
                .limit(TOP)
                .toList();
    }
}
