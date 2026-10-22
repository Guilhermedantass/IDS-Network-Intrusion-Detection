package dev.guilhermedantas.ids.sensor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;

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

/** Heartbeat do sensor, lista e pedidos do dashboard. Cada teste usa um nome de sensor proprio. */
@Import(TestcontainersConfiguration.class)
@SpringBootTest
@AutoConfigureMockMvc
class SensorControllerTests {

    @Autowired
    MockMvc mvc;

    @Autowired
    SensorRegistry registry;

    @Value("${ids.dashboard-origin}")
    String dashboardOrigin;

    @Test
    void sensorNovoAdotaOEstadoAtual() throws Exception {
        heartbeat("s-adota", true, "lo")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.capture").value(true))
                .andExpect(jsonPath("$.interface").value("lo"));
    }

    @Test
    void dashboardPedeEOSensorRecebeNoProximoHeartbeat() throws Exception {
        heartbeat("s-pede", false, null).andExpect(jsonPath("$.capture").value(false));

        mvc.perform(put("/api/sensors/{name}/capture", "s-pede").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"capture\": true, \"interface\": \"eth9\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.desired.capture").value(true))
                .andExpect(jsonPath("$.reported.capturing").value(false));   // ainda nao aplicou

        heartbeat("s-pede", false, null)
                .andExpect(jsonPath("$.capture").value(true))
                .andExpect(jsonPath("$.interface").value("eth9"));
    }

    @Test
    void listaMostraOEstadoEOPedido() throws Exception {
        heartbeat("s-lista", true, "lo");
        mvc.perform(get("/api/sensors"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[?(@.name == 's-lista')].online").value(true))
                .andExpect(jsonPath("$[?(@.name == 's-lista')].reported.interface").value("lo"))
                .andExpect(jsonPath("$[?(@.name == 's-lista')].reported.flows").value(10))
                .andExpect(jsonPath("$[?(@.name == 's-lista')].desired.capture").value(true));
    }

    @Test
    void semHeartbeatHa15SegundosFicaOffline() throws Exception {
        heartbeat("s-offline", false, null);
        Instant later = Instant.now().plusSeconds(16);
        assertThat(registry.list(later)).filteredOn(s -> s.name().equals("s-offline"))
                .singleElement().extracting(SensorView::online).isEqualTo(false);
    }

    @Test
    void pedidoParaSensorDesconhecidoOuInterfaceQueNaoExiste() throws Exception {
        mvc.perform(put("/api/sensors/{name}/capture", "s-nao-existe").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"capture\": true, \"interface\": null}"))
                .andExpect(status().isNotFound());

        heartbeat("s-iface", false, null);
        mvc.perform(put("/api/sensors/{name}/capture", "s-iface").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"capture\": true, \"interface\": \"wlan42\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void heartbeatSemNomeERecusado() throws Exception {
        mvc.perform(post("/api/sensors/heartbeat").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"sensor\": \"\", \"capturing\": false, \"interfaces\": []}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void dashboardPodeFazerPutNosSensoresMasNaoPostDeAlertas() throws Exception {
        mvc.perform(options("/api/sensors/x/capture")
                        .header(HttpHeaders.ORIGIN, dashboardOrigin)
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "PUT"))
                .andExpect(status().isOk());
        mvc.perform(options("/api/alerts")
                        .header(HttpHeaders.ORIGIN, dashboardOrigin)
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "POST"))
                .andExpect(status().isForbidden());
    }

    private org.springframework.test.web.servlet.ResultActions heartbeat(String sensor, boolean capturing, String iface)
            throws Exception {
        String ifaceJson = iface == null ? "null" : "\"" + iface + "\"";
        String body = """
                {"sensor": "%s", "capturing": %s, "interface": %s, "startedAt": null, "flows": 10, "attacks": 2,
                 "alertsSent": 1, "interfaces": ["eth9", "lo"], "error": null}
                """.formatted(sensor, capturing, ifaceJson);
        return mvc.perform(post("/api/sensors/heartbeat").contentType(MediaType.APPLICATION_JSON).content(body));
    }
}
