package dev.guilhermedantas.ids.incident;

import java.util.List;

import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionalEventListener;

/**
 * Avisa o dashboard (WebSocket, /topic/incidents) quando incidentes abrem ou mudam.
 *
 * So depois do commit: se o lote der erro e a transacao for desfeita, o dashboard nao fica
 * mostrando um incidente que nao existe no banco.
 */
@Component
class IncidentNotifier {

    static final String TOPIC = "/topic/incidents";

    /** Evento publicado pelo IncidentService: os incidentes que um lote abriu ou mudou. */
    record IncidentsChanged(List<IncidentMessage> incidents) {
    }

    private final SimpMessagingTemplate messaging;

    IncidentNotifier(SimpMessagingTemplate messaging) {
        this.messaging = messaging;
    }

    @TransactionalEventListener   // padrao: phase = AFTER_COMMIT
    void onIncidentsChanged(IncidentsChanged event) {
        event.incidents().forEach(msg -> messaging.convertAndSend(TOPIC, msg));
    }
}
