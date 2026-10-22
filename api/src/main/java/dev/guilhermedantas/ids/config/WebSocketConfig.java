package dev.guilhermedantas.ids.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.web.socket.config.annotation.EnableWebSocketMessageBroker;
import org.springframework.web.socket.config.annotation.StompEndpointRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;

/**
 * WebSocket com STOMP para o dashboard ao vivo.
 *
 * O dashboard conecta em ws://localhost:8080/ws e assina os topicos:
 *   /topic/incidents   um IncidentMessage cada vez que um incidente abre ou muda
 */
@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    private final String dashboardOrigin;

    public WebSocketConfig(@Value("${ids.dashboard-origin}") String dashboardOrigin) {
        this.dashboardOrigin = dashboardOrigin;
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        // so o dashboard pode conectar pelo navegador (os navegadores mandam o cabecalho Origin)
        registry.addEndpoint("/ws").setAllowedOrigins(dashboardOrigin);
    }

    @Override
    public void configureMessageBroker(MessageBrokerRegistry registry) {
        // broker simples, em memoria: entrega para quem assinou /topic/...
        registry.enableSimpleBroker("/topic");
    }
}
