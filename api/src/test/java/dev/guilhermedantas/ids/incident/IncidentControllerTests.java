package dev.guilhermedantas.ids.incident;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import dev.guilhermedantas.ids.TestcontainersConfiguration;
import dev.guilhermedantas.ids.alert.AlertRepository;

/** GET /api/incidents: a lista que o dashboard busca ao abrir. */
@Import(TestcontainersConfiguration.class)
@SpringBootTest
@AutoConfigureMockMvc
class IncidentControllerTests {

    @Autowired
    MockMvc mvc;

    @Autowired
    AlertRepository alerts;

    @Autowired
    IncidentRepository incidents;

    @Value("${ids.dashboard-origin}")
    String dashboardOrigin;

    @BeforeEach
    void tresIncidentes() throws Exception {
        alerts.deleteAll();
        incidents.deleteAll();
        // tres destinos diferentes = tres incidentes; o 10.0.0.2 e o mais recente
        String body = """
                {"sensor": "teste", "alerts": [
                  %s, %s, %s
                ]}
                """.formatted(alerta("13:00:00Z", "10.0.0.1"), alerta("13:05:00Z", "10.0.0.2"),
                alerta("13:02:00Z", "10.0.0.3"));
        mvc.perform(post("/api/alerts").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isCreated());
    }

    @Test
    void listaOsMaisRecentesPrimeiro() throws Exception {
        mvc.perform(get("/api/incidents"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(3))
                .andExpect(jsonPath("$[0].dstIp").value("10.0.0.2"))
                .andExpect(jsonPath("$[1].dstIp").value("10.0.0.3"))
                .andExpect(jsonPath("$[2].dstIp").value("10.0.0.1"))
                .andExpect(jsonPath("$[0].lastSeenAt").value("2026-10-22T13:05:00Z"))
                .andExpect(jsonPath("$[0].alertCount").value(1));
    }

    @Test
    void limitCortaALista() throws Exception {
        mvc.perform(get("/api/incidents").param("limit", "2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].dstIp").value("10.0.0.2"));
    }

    @Test
    void limitForaDaFaixaERecusado() throws Exception {
        mvc.perform(get("/api/incidents").param("limit", "0")).andExpect(status().isBadRequest());
        mvc.perform(get("/api/incidents").param("limit", "501")).andExpect(status().isBadRequest());
    }

    @Test
    void dashboardPodeLerPeloNavegador() throws Exception {
        mvc.perform(get("/api/incidents").header(HttpHeaders.ORIGIN, dashboardOrigin))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, dashboardOrigin));
    }

    @Test
    void outroSiteNaoPode() throws Exception {
        mvc.perform(get("/api/incidents").header(HttpHeaders.ORIGIN, "http://site-estranho.com"))
                .andExpect(status().isForbidden());
    }

    @Test
    void navegadorNaoPodeMandarAlertas() throws Exception {
        // preflight do navegador para um POST: so GET esta liberado no CORS
        mvc.perform(options("/api/alerts")
                        .header(HttpHeaders.ORIGIN, dashboardOrigin)
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "POST"))
                .andExpect(status().isForbidden());
    }

    private static String alerta(String hora, String dstIp) {
        return """
                {"ts": "2026-10-22T%s", "type": "SYN Flood", "detectedBy": "volume",
                 "dstIp": "%s", "protocol": "TCP", "rate": 100.0}
                """.formatted(hora, dstIp);
    }
}
