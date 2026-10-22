package dev.guilhermedantas.ids.alert;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

/**
 * O Spring Data gera a implementacao (save, saveAll, findAll, findById...) em tempo de execucao.
 * Consultas novas saem do nome do metodo, ex.: List<Alert> findByDstIpOrderByTsDesc(String dstIp).
 */
public interface AlertRepository extends JpaRepository<Alert, Long> {

    /** Os alertas de um incidente, do primeiro ao ultimo. IncidentId = o campo id dentro de incident. */
    List<Alert> findByIncidentIdOrderByTsAsc(Long incidentId);
}
