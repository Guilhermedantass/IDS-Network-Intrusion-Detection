package dev.guilhermedantas.ids.alert;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import dev.guilhermedantas.ids.TestcontainersConfiguration;

/** POST /api/alerts de ponta a ponta: HTTP -> validacao -> banco (PostgreSQL do Testcontainers). */
@Import(TestcontainersConfiguration.class)
@SpringBootTest
@AutoConfigureMockMvc
class AlertControllerTests {

    // o mesmo formato que o sensor manda (sensor/src/alerts.py)
    private static final String VALIDO = """
            {"sensor": "teste", "alerts": [
              {"ts": "2026-10-22T13:33:19Z", "type": "SYN Flood", "detectedBy": "volume",
               "srcIp": "127.0.0.1", "dstIp": "127.0.0.1", "dstPort": 9, "protocol": "TCP",
               "flows": null, "packets": 1800, "rate": 180.0, "ports": 1, "sources": null, "probability": null},
              {"ts": "2026-10-22T13:33:20Z", "type": "PortScan", "detectedBy": "modelo",
               "srcIp": "10.0.0.5", "dstIp": "10.0.0.1", "dstPort": null, "protocol": "TCP",
               "flows": 120, "packets": null, "rate": null, "ports": 98, "sources": null, "probability": 0.97}
            ]}
            """;

    @Autowired
    MockMvc mvc;

    @Autowired
    AlertRepository repository;

    @BeforeEach
    void limparBanco() {
        repository.deleteAll();
    }

    @Test
    void loteValidoSalvaTodosOsAlertas() throws Exception {
        mvc.perform(post("/api/alerts").contentType(MediaType.APPLICATION_JSON).content(VALIDO))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.saved").value(2));

        assertThat(repository.count()).isEqualTo(2);
    }

    @Test
    void alertaSemDstIpRecusaOLoteInteiro() throws Exception {
        String semDstIp = """
                {"sensor": "teste", "alerts": [
                  {"ts": "2026-10-22T13:33:19Z", "type": "SYN Flood", "detectedBy": "volume", "protocol": "TCP"}
                ]}
                """;

        mvc.perform(post("/api/alerts").contentType(MediaType.APPLICATION_JSON).content(semDstIp))
                .andExpect(status().isBadRequest());

        assertThat(repository.count()).isZero();
    }

    @Test
    void loteVazioERecusado() throws Exception {
        mvc.perform(post("/api/alerts").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"sensor\": \"teste\", \"alerts\": []}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void jsonMalFormadoERecusado() throws Exception {
        mvc.perform(post("/api/alerts").contentType(MediaType.APPLICATION_JSON).content("{\"sensor\": "))
                .andExpect(status().isBadRequest());
    }
}
