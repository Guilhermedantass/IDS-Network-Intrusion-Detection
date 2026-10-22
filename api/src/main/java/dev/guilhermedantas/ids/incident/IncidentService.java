package dev.guilhermedantas.ids.incident;

import java.time.Duration;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.domain.Limit;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import dev.guilhermedantas.ids.incident.IncidentNotifier.IncidentsChanged;

/**
 * Agrupa alertas em incidentes. Mesmo ataque = mesmo sensor + type + dstIp, com no maximo GAP entre um
 * alerta e o seguinte; passou disso, o ataque acabou e o proximo alerta abre um incidente novo.
 */
@Service
public class IncidentService {

    /** 6 janelas de 10 s do sensor/src/volume.py sem alerta. */
    static final Duration GAP = Duration.ofSeconds(60);

    private final IncidentRepository repository;
    private final ApplicationEventPublisher events;

    public IncidentService(IncidentRepository repository, ApplicationEventPublisher events) {
        this.repository = repository;
        this.events = events;
    }

    /** Os incidentes mais recentes (pelo ultimo alerta), para o dashboard montar a lista ao abrir. */
    @Transactional(readOnly = true)
    public List<IncidentMessage> recent(int limit) {
        return repository.findAllByOrderByLastSeenAtDesc(Limit.of(limit)).stream()
                .map(IncidentMessage::from)
                .toList();
    }

    /** Um incidente pelo id (pagina de detalhe); vazio se nao existe. */
    @Transactional(readOnly = true)
    public Optional<IncidentMessage> find(long id) {
        return repository.findById(id).map(IncidentMessage::from);
    }

    /**
     * Avisa que estes incidentes abriram ou mudaram. A mensagem sai pelo WebSocket so depois do
     * commit (IncidentNotifier); um incidente que recebeu varios alertas do lote vai uma vez so.
     */
    public void publish(Collection<Incident> changed) {
        if (!changed.isEmpty()) {
            events.publishEvent(new IncidentsChanged(changed.stream().map(IncidentMessage::from).toList()));
        }
    }

    /** Coloca o alerta no incidente aberto do mesmo ataque, ou abre um novo. Devolve o incidente. */
    @Transactional
    public Incident register(String sensor, String type, String dstIp, Instant ts, Double rate) {
        return repository.findFirstBySensorAndTypeAndDstIpOrderByLastSeenAtDesc(sensor, type, dstIp)
                .filter(incident -> !ts.isAfter(incident.getLastSeenAt().plus(GAP)))
                .map(incident -> {
                    incident.addAlert(ts, rate);   // sem save: o Hibernate grava a mudanca no fim da transacao
                    return incident;
                })
                .orElseGet(() -> repository.save(new Incident(sensor, type, dstIp, ts, rate)));
    }
}
