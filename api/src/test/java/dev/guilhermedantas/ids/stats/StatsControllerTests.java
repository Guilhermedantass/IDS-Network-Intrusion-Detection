package dev.guilhermedantas.ids.stats;

import static java.time.temporal.ChronoUnit.HOURS;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import dev.guilhermedantas.ids.TestcontainersConfiguration;
import dev.guilhermedantas.ids.alert.AlertRepository;
import dev.guilhermedantas.ids.incident.IncidentRepository;

/** GET /api/stats: as contas da visao geral, com alertas em horarios relativos a agora. */
@Import(TestcontainersConfiguration.class)
@SpringBootTest
@AutoConfigureMockMvc
class StatsControllerTests {

    @Autowired
    MockMvc mvc;

    @Autowired
    AlertRepository alerts;

    @Autowired
    IncidentRepository incidents;

    // horas cheias relativas a agora, para o teste nao depender de que horas ele roda
    final Instant thisHour = Instant.now().truncatedTo(HOURS);

    @BeforeEach
    void dados() throws Exception {
        alerts.deleteAll();
        incidents.deleteAll();
        enviar(
                // SYN Flood de 10.9.9.9 contra 10.0.0.1, 40 s de duracao (2 alertas, um incidente)
                alerta(thisHour.plusSeconds(1), "SYN Flood", "10.9.9.9", "10.0.0.1", 150.0),
                alerta(thisHour.plusSeconds(41), "SYN Flood", "10.9.9.9", "10.0.0.1", 300.0),
                // PortScan de 10.9.9.9 contra 10.0.0.2
                alerta(thisHour.plusSeconds(3), "PortScan", "10.9.9.9", "10.0.0.2", 80.0),
                // DDoS sem origem (muitas) contra 10.0.0.1, 3 horas atras
                alerta(thisHour.minus(3, HOURS), "DDoS", null, "10.0.0.1", 900.0),
                // fora das 24 h: nao entra em nada
                alerta(thisHour.minus(30, HOURS), "UDP Flood", "10.7.7.7", "10.0.0.4", 5000.0));
    }

    @Test
    void totaisEPorTipo() throws Exception {
        mvc.perform(get("/api/stats"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.since").value(thisHour.minus(23, HOURS).toString()))
                .andExpect(jsonPath("$.incidents").value(3))
                .andExpect(jsonPath("$.alerts").value(4))
                .andExpect(jsonPath("$.byType.length()").value(3));
    }

    @Test
    void porHoraComOsTipos() throws Exception {
        mvc.perform(get("/api/stats"))
                .andExpect(jsonPath("$.byHour.length()").value(24))
                .andExpect(jsonPath("$.byHour[23].hour").value(thisHour.toString()))
                .andExpect(jsonPath("$.byHour[23].incidents").value(2))
                .andExpect(jsonPath("$.byHour[23].byType['SYN Flood']").value(1))
                .andExpect(jsonPath("$.byHour[23].byType['PortScan']").value(1))
                .andExpect(jsonPath("$.byHour[20].byType['DDoS']").value(1))
                .andExpect(jsonPath("$.byHour[0].incidents").value(0));
    }

    @Test
    void destaques() throws Exception {
        mvc.perform(get("/api/stats"))
                .andExpect(jsonPath("$.highestRate.type").value("DDoS"))
                .andExpect(jsonPath("$.highestRate.value").value(900.0))
                .andExpect(jsonPath("$.longest.type").value("SYN Flood"))
                .andExpect(jsonPath("$.longest.value").value(40.0))
                .andExpect(jsonPath("$.longest.incidentId").isNumber());
    }

    @Test
    void origensEAlvos() throws Exception {
        mvc.perform(get("/api/stats"))
                // o DDoS nao tem origem: so os 3 alertas de 10.9.9.9, em 2 incidentes
                .andExpect(jsonPath("$.topSources.length()").value(1))
                .andExpect(jsonPath("$.topSources[0].ip").value("10.9.9.9"))
                .andExpect(jsonPath("$.topSources[0].alerts").value(3))
                .andExpect(jsonPath("$.topSources[0].incidents").value(2))
                // 10.0.0.1: SYN Flood (2 alertas) + DDoS (1) = 3 alertas em 2 incidentes
                .andExpect(jsonPath("$.topTargets[0].ip").value("10.0.0.1"))
                .andExpect(jsonPath("$.topTargets[0].alerts").value(3))
                .andExpect(jsonPath("$.topTargets[0].incidents").value(2))
                .andExpect(jsonPath("$.topTargets[1].ip").value("10.0.0.2"));
    }

    @Test
    void semIncidentesOsDestaquesVemVazios() throws Exception {
        alerts.deleteAll();
        incidents.deleteAll();
        mvc.perform(get("/api/stats"))
                .andExpect(jsonPath("$.incidents").value(0))
                .andExpect(jsonPath("$.highestRate").doesNotExist())
                .andExpect(jsonPath("$.longest").doesNotExist())
                .andExpect(jsonPath("$.topSources.length()").value(0));
    }

    @Test
    void horasForaDaFaixaSaoRecusadas() throws Exception {
        mvc.perform(get("/api/stats").param("hours", "0")).andExpect(status().isBadRequest());
        mvc.perform(get("/api/stats").param("hours", "169")).andExpect(status().isBadRequest());
    }

    private void enviar(String... alertas) throws Exception {
        String body = "{\"sensor\": \"teste\", \"alerts\": [" + String.join(",", alertas) + "]}";
        mvc.perform(post("/api/alerts").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isCreated());
    }

    private static String alerta(Instant ts, String type, String srcIp, String dstIp, double rate) {
        String src = srcIp == null ? "null" : "\"" + srcIp + "\"";
        return """
                {"ts": "%s", "type": "%s", "detectedBy": "volume", "srcIp": %s, "dstIp": "%s",
                 "protocol": "TCP", "rate": %s}
                """.formatted(ts, type, src, dstIp, rate);
    }
}
