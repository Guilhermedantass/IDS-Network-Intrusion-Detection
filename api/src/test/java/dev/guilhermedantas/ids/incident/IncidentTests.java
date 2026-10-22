package dev.guilhermedantas.ids.incident;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;
import java.util.Comparator;
import java.util.List;

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

/** Agrupamento de alertas em incidentes, mandando lotes pelo POST /api/alerts como o sensor faz. */
@Import(TestcontainersConfiguration.class)
@SpringBootTest
@AutoConfigureMockMvc
class IncidentTests {

    @Autowired
    MockMvc mvc;

    @Autowired
    AlertRepository alerts;

    @Autowired
    IncidentRepository incidents;

    @BeforeEach
    void limparBanco() {
        alerts.deleteAll();      // primeiro os alertas: eles apontam para os incidentes
        incidents.deleteAll();
    }

    @Test
    void alertasDoMesmoAtaqueViramUmIncidente() throws Exception {
        // fora de ordem de proposito: a API ordena pelo ts
        enviar(volume("13:00:20Z", "10.0.0.1", 150.0),
               volume("13:00:00Z", "10.0.0.1", 180.0),
               volume("13:00:10Z", "10.0.0.1", 120.0));

        Incident incident = unico();
        assertThat(incident.getAlertCount()).isEqualTo(3);
        assertThat(incident.getStartedAt()).isEqualTo(ts("13:00:00Z"));
        assertThat(incident.getLastSeenAt()).isEqualTo(ts("13:00:20Z"));
        assertThat(incident.getPeakRate()).isEqualTo(180.0);
    }

    @Test
    void lotesSeparadosJuntamNoMesmoIncidente() throws Exception {
        enviar(volume("13:00:00Z", "10.0.0.1", 100.0));
        enviar(volume("13:00:50Z", "10.0.0.1", 200.0));   // 50 s depois: dentro do GAP

        Incident incident = unico();
        assertThat(incident.getAlertCount()).isEqualTo(2);
        assertThat(incident.getPeakRate()).isEqualTo(200.0);
    }

    @Test
    void pausaMaiorQueOGapAbreOutroIncidente() throws Exception {
        enviar(volume("13:00:00Z", "10.0.0.1", 100.0));
        enviar(volume("13:01:01Z", "10.0.0.1", 100.0));   // 61 s depois: o ataque anterior acabou

        List<Incident> lista = todos();
        assertThat(lista).hasSize(2);
        assertThat(lista).allSatisfy(i -> assertThat(i.getAlertCount()).isEqualTo(1));
    }

    @Test
    void destinosDiferentesSaoIncidentesDiferentes() throws Exception {
        enviar(volume("13:00:00Z", "10.0.0.1", 100.0),
               volume("13:00:00Z", "10.0.0.2", 100.0));

        assertThat(todos()).extracting(Incident::getDstIp).containsExactly("10.0.0.1", "10.0.0.2");
    }

    @Test
    void alertaDoModeloNaoTemPico() throws Exception {
        enviar("""
                {"ts": "2026-10-22T13:00:00Z", "type": "PortScan", "detectedBy": "modelo", "srcIp": "10.0.0.5",
                 "dstIp": "10.0.0.1", "protocol": "TCP", "flows": 120, "ports": 98, "probability": 0.97}
                """);

        assertThat(unico().getPeakRate()).isNull();
    }

    // --- ajudantes

    private void enviar(String... alertas) throws Exception {
        String body = "{\"sensor\": \"teste\", \"alerts\": [" + String.join(",", alertas) + "]}";
        mvc.perform(post("/api/alerts").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isCreated());
    }

    private static String volume(String hora, String dstIp, double rate) {
        return """
                {"ts": "%s", "type": "SYN Flood", "detectedBy": "volume", "srcIp": "10.0.0.9",
                 "dstIp": "%s", "dstPort": 9, "protocol": "TCP", "packets": 1800, "rate": %s, "ports": 1}
                """.formatted(ts(hora), dstIp, rate);
    }

    private static Instant ts(String hora) {
        return Instant.parse("2026-10-22T" + hora);
    }

    private List<Incident> todos() {
        return incidents.findAll().stream().sorted(Comparator.comparing(Incident::getDstIp)).toList();
    }

    private Incident unico() {
        List<Incident> lista = todos();
        assertThat(lista).hasSize(1);
        return lista.getFirst();
    }
}
