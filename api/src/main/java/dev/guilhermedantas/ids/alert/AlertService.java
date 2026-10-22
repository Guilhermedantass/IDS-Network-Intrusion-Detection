package dev.guilhermedantas.ids.alert;

/**
 * Regras de negocio dos alertas. O controller so recebe o HTTP e chama o service.
 *
 * TODO:
 *   - anotar com @Service
 *   - receber o AlertRepository pelo construtor (injecao de dependencia; sem @Autowired em campo)
 *   - metodo "int save(AlertBatchRequest batch)": converte cada AlertRequest com Alert.from(...),
 *     salva todos com saveAll e devolve quantos foram salvos
 *   - @Transactional no metodo: ou salva o lote inteiro, ou nada
 *
 * Proximo passo (depois que isto funcionar): agrupar alertas em incidentes e avisar o
 * dashboard por WebSocket. Vai ser aqui que essa logica entra.
 */
public class AlertService {
}
