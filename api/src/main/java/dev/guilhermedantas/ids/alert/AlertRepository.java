package dev.guilhermedantas.ids.alert;

import org.springframework.data.jpa.repository.JpaRepository;

/**
 * O Spring Data gera a implementacao (save, saveAll, findAll, findById...) em tempo de execucao.
 * Consultas novas saem do nome do metodo, ex.: List<Alert> findByDstIpOrderByTsDesc(String dstIp).
 */
public interface AlertRepository extends JpaRepository<Alert, Long> {
}
