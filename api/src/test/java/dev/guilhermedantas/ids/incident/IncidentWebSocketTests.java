package dev.guilhermedantas.ids.incident;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.Type;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.annotation.Import;
import org.springframework.messaging.converter.JacksonJsonMessageConverter;
import org.springframework.messaging.simp.stomp.StompFrameHandler;
import org.springframework.messaging.simp.stomp.StompHeaders;
import org.springframework.messaging.simp.stomp.StompSession;
import org.springframework.messaging.simp.stomp.StompSessionHandlerAdapter;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.socket.WebSocketHttpHeaders;
import org.springframework.web.socket.client.standard.StandardWebSocketClient;
import org.springframework.web.socket.messaging.WebSocketStompClient;

import dev.guilhermedantas.ids.TestcontainersConfiguration;
import dev.guilhermedantas.ids.alert.AlertRepository;

/** O dashboard recebe os incidentes pelo WebSocket: conecta em /ws como o Angular vai fazer. */
@Import(TestcontainersConfiguration.class)
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)   // servidor de verdade, numa porta livre
class IncidentWebSocketTests {

    @LocalServerPort
    int port;

    @Value("${ids.dashboard-origin}")
    String dashboardOrigin;

    @Autowired
    AlertRepository alerts;

    @Autowired
    IncidentRepository incidents;

    @Autowired
    IncidentService service;

    @Autowired
    TransactionTemplate tx;

    final BlockingQueue<IncidentMessage> recebidas = new LinkedBlockingQueue<>();
    StompSession session;

    @BeforeEach
    void conectar() throws Exception {
        alerts.deleteAll();
        incidents.deleteAll();

        WebSocketStompClient client = new WebSocketStompClient(new StandardWebSocketClient());
        client.setMessageConverter(new JacksonJsonMessageConverter());

        WebSocketHttpHeaders headers = new WebSocketHttpHeaders();
        headers.setOrigin(dashboardOrigin);   // como o navegador faria
        session = client.connectAsync("ws://localhost:" + port + "/ws", headers, new StompSessionHandlerAdapter() {})
                .get(5, TimeUnit.SECONDS);

        session.subscribe(IncidentNotifier.TOPIC, new StompFrameHandler() {
            @Override
            public Type getPayloadType(StompHeaders h) {
                return IncidentMessage.class;
            }

            @Override
            public void handleFrame(StompHeaders h, Object payload) {
                recebidas.add((IncidentMessage) payload);
            }
        });
        Thread.sleep(300);   // o SUBSCRIBE e assincrono: espera o broker registrar antes de mandar alertas
    }

    @AfterEach
    void desconectar() {
        session.disconnect();
    }

    @Test
    void loteComVariosAlertasDoMesmoAtaqueMandaUmaMensagem() throws Exception {
        int status = enviar(volume("13:00:00Z", 100.0, "TCP"), volume("13:00:10Z", 180.0, "TCP"),
                volume("13:00:20Z", 150.0, "TCP"));
        assertThat(status).isEqualTo(201);

        IncidentMessage msg = recebidas.poll(5, TimeUnit.SECONDS);
        assertThat(msg).isNotNull();
        assertThat(msg.type()).isEqualTo("SYN Flood");
        assertThat(msg.alertCount()).isEqualTo(3);
        assertThat(msg.peakRate()).isEqualTo(180.0);

        assertThat(recebidas.poll(500, TimeUnit.MILLISECONDS)).isNull();   // so uma
    }

    @Test
    void loteComErroNoBancoNaoDeixaIncidente() throws Exception {
        // protocol maior que VARCHAR(10): o incidente chega a ser criado, mas o INSERT do alerta falha
        // e a transacao inteira e desfeita
        int status = enviar(volume("13:00:00Z", 100.0, "PROTOCOLO-GRANDE"));
        assertThat(status).isEqualTo(500);

        assertThat(recebidas.poll(1, TimeUnit.SECONDS)).isNull();
        assertThat(incidents.count()).isZero();
    }

    @Test
    void transacaoDesfeitaDepoisDoPublishNaoAvisaODashboard() throws Exception {
        // o publish acontece, mas a transacao e desfeita depois: a mensagem nao pode sair
        tx.executeWithoutResult(status -> {
            Incident i = service.register("teste", "SYN Flood", "10.0.0.1", Instant.parse("2026-10-22T13:00:00Z"), 100.0);
            service.publish(List.of(i));
            status.setRollbackOnly();
        });

        assertThat(recebidas.poll(1, TimeUnit.SECONDS)).isNull();
    }

    // --- ajudantes

    private int enviar(String... alertas) throws Exception {
        String body = "{\"sensor\": \"teste\", \"alerts\": [" + String.join(",", alertas) + "]}";
        HttpRequest req = HttpRequest.newBuilder(URI.create("http://localhost:" + port + "/api/alerts"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
        try (HttpClient http = HttpClient.newHttpClient()) {
            return http.send(req, HttpResponse.BodyHandlers.discarding()).statusCode();
        }
    }

    private static String volume(String hora, double rate, String protocol) {
        return """
                {"ts": "2026-10-22T%s", "type": "SYN Flood", "detectedBy": "volume",
                 "dstIp": "10.0.0.1", "protocol": "%s", "rate": %s}
                """.formatted(hora, protocol, rate);
    }
}
