package dev.guilhermedantas.ids.alert;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Regras de negocio dos alertas. O controller so recebe o HTTP e chama o service.
 *
 * Proximo passo (depois que isto funcionar): agrupar alertas em incidentes e avisar o
 * dashboard por WebSocket. Vai ser aqui que essa logica entra.
 */
@Service
public class AlertService {

    private final AlertRepository repository;

    public AlertService(AlertRepository repository) {
        this.repository = repository;
    }

    /** Salva o lote inteiro ou nada, e devolve quantos alertas foram salvos. */
    @Transactional
    public int save(AlertBatchRequest batch) {
        List<Alert> alerts = batch.alerts().stream()
                .map(req -> Alert.from(batch.sensor(), req))
                .toList();
        return repository.saveAll(alerts).size();
    }
}
