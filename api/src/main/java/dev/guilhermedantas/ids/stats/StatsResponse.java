package dev.guilhermedantas.ids.stats;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Resumo das ultimas horas para a visao geral do dashboard (GET /api/stats?hours=24).
 *
 * @param since      inicio da janela (comeco da hora mais antiga)
 * @param incidents  incidentes que comecaram na janela
 * @param alerts     alertas vistos na janela
 * @param highestRate o incidente com o maior pico de pacotes/s (null se nenhum tem taxa)
 * @param longest    o incidente mais longo, do primeiro ao ultimo alerta, em segundos (null se nao ha incidentes)
 * @param byType     incidentes por tipo, do mais comum ao menos
 * @param byHour     incidentes por hora (pelo inicio), uma entrada por hora da janela, inclusive as zeradas
 * @param topSources IPs de origem com mais alertas (sem os alertas sem origem, como o DDoS), ate 5
 * @param topTargets IPs de destino com mais alertas, ate 5
 */
public record StatsResponse(
        Instant since,
        int incidents,
        long alerts,
        Highlight highestRate,
        Highlight longest,
        List<TypeCount> byType,
        List<HourCount> byHour,
        List<IpCount> topSources,
        List<IpCount> topTargets) {

    /** Um numero de destaque e o incidente de onde ele veio (o dashboard linka para ele). */
    public record Highlight(long incidentId, String type, double value) {
    }

    public record TypeCount(String type, long incidents) {
    }

    /** byType: so os tipos que tiveram incidente naquela hora. */
    public record HourCount(Instant hour, long incidents, Map<String, Long> byType) {
    }

    public record IpCount(String ip, long incidents, long alerts) {
    }
}
