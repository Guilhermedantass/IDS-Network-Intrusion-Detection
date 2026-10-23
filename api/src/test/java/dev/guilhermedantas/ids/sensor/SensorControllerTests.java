package dev.guilhermedantas.ids.sensor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
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
    void bloquearEDesbloquearChegamNoHeartbeat() throws Exception {
        heartbeat("s-bloqueio", false, null).andExpect(jsonPath("$.blocked").isEmpty());

        mvc.perform(put("/api/sensors/{name}/blocked/{ip}", "s-bloqueio", "10.0.0.5"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.desired.blocked[0]").value("10.0.0.5"));
        mvc.perform(put("/api/sensors/{name}/blocked/{ip}", "s-bloqueio", "2001:db8::7"));
        mvc.perform(put("/api/sensors/{name}/blocked/{ip}", "s-bloqueio", "10.0.0.5"));   // repetido: nao duplica
        heartbeat("s-bloqueio", false, null).andExpect(jsonPath("$.blocked.length()").value(2));

        mvc.perform(delete("/api/sensors/{name}/blocked/{ip}", "s-bloqueio", "10.0.0.5")).andExpect(status().isOk());
        heartbeat("s-bloqueio", false, null)
                .andExpect(jsonPath("$.blocked.length()").value(1))
                .andExpect(jsonPath("$.blocked[0]").value("2001:db8::7"))
                .andExpect(jsonPath("$.capture").value(false));      // a captura nao muda
    }

    @Test
    void naoBloqueiaProtegidosNemTextoQueNaoEIp() throws Exception {
        heartbeat("s-protegido", false, null);
        for (String ip : new String[] {"127.0.0.1", "::1", "192.168.0.1", "0:0:0:0:0:ffff:c0a8:1", "pc-do-vizinho"}) {
            mvc.perform(put("/api/sensors/{name}/blocked/{ip}", "s-protegido", ip)).andExpect(status().isBadRequest());
        }
        mvc.perform(put("/api/sensors/{name}/blocked/{ip}", "s-nao-existe", "10.0.0.5")).andExpect(status().isNotFound());
    }

    @Test
    void apiReiniciadaAdotaOsBloqueiosDoSensor() throws Exception {
        String body = """
                {"sensor": "s-adota-bloqueio", "capturing": false, "flows": 0, "attacks": 0, "alertsSent": 0,
                 "interfaces": [], "blocked": ["10.0.0.9"]}
                """;
        mvc.perform(post("/api/sensors/heartbeat").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(jsonPath("$.blocked[0]").value("10.0.0.9"));
    }

    @Test
    void mudarACapturaNaoMexeNosBloqueios() throws Exception {
        heartbeat("s-captura-bloqueio", false, null);
        mvc.perform(put("/api/sensors/{name}/blocked/{ip}", "s-captura-bloqueio", "10.0.0.5"));
        mvc.perform(put("/api/sensors/{name}/capture", "s-captura-bloqueio").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"capture\": true, \"interface\": \"lo\"}"))
                .andExpect(jsonPath("$.desired.blocked[0]").value("10.0.0.5"));
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
        mvc.perform(options("/api/sensors/x/blocked/10.0.0.5")
                        .header(HttpHeaders.ORIGIN, dashboardOrigin)
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "DELETE"))
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
                 "alertsSent": 1, "interfaces": ["eth9", "lo"], "error": null,
                 "blocked": [], "protected": ["192.168.0.1", "172.32.1.56"], "blockError": null}
                """.formatted(sensor, capturing, ifaceJson);
        return mvc.perform(post("/api/sensors/heartbeat").contentType(MediaType.APPLICATION_JSON).content(body));
    }
}
