package dev.guilhermedantas.ids.alert;

/**
 * TODO: transformar em "public interface AlertRepository extends JpaRepository<Alert, Long>".
 * So isso: o Spring Data gera a implementacao (save, saveAll, findAll, findById...) em tempo de execucao.
 * Depois, consultas novas saem do nome do metodo, ex.: List<Alert> findByDstIpOrderByTsDesc(String dstIp).
 */
final class AlertRepository {
    private AlertRepository() {
    }
}
