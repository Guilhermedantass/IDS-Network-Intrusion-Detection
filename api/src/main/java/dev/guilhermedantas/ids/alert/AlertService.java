package dev.guilhermedantas.ids.alert;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import dev.guilhermedantas.ids.incident.Incident;
import dev.guilhermedantas.ids.incident.IncidentService;

/**
 * Regras de negocio dos alertas. O controller so recebe o HTTP e chama o service.
 * Cada alerta salvo entra em um incidente (incident/IncidentService).
 */
@Service
public class AlertService {

    private final AlertRepository repository;
    private final IncidentService incidents;

    public AlertService(AlertRepository repository, IncidentService incidents) {
        this.repository = repository;
        this.incidents = incidents;
    }

    /** Salva o lote inteiro ou nada (alertas e incidentes), e devolve quantos alertas foram salvos. */
    @Transactional
    public int save(AlertBatchRequest batch) {
        // em ordem de tempo: o lote pode vir fora de ordem, e o GAP do incidente conta a partir do alerta anterior
        List<AlertRequest> reqs = batch.alerts().stream()
                .sorted(Comparator.comparing(AlertRequest::ts))
                .toList();

        List<Alert> alerts = new ArrayList<>();
        Set<Incident> changed = new LinkedHashSet<>();   // Set: cada incidente uma vez, mesmo com varios alertas
        for (AlertRequest req : reqs) {
            Incident incident = incidents.register(batch.sensor(), req.type(), req.dstIp(), req.ts(), req.rate());
            alerts.add(Alert.from(batch.sensor(), req, incident));
            changed.add(incident);
        }
        int saved = repository.saveAll(alerts).size();
        incidents.publish(changed);
        return saved;
    }

    /** Os alertas de um incidente, em ordem de tempo (lista vazia se o incidente nao existe). */
    @Transactional(readOnly = true)
    public List<AlertResponse> byIncident(long incidentId) {
        return repository.findByIncident_IdOrderByTsAsc(incidentId).stream()
                .map(Alert::toResponse)
                .toList();
    }
}
