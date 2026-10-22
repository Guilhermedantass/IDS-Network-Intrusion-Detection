package dev.guilhermedantas.ids.alert;

import java.time.Instant;
import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

/**
 * O Spring Data gera a implementacao (save, saveAll, findAll, findById...) em tempo de execucao.
 * Consultas novas saem do nome do metodo, ex.: List<Alert> findByDstIpOrderByTsDesc(String dstIp).
 */
public interface AlertRepository extends JpaRepository<Alert, Long> {

    /**
     * Os alertas de um incidente, do primeiro ao ultimo. O _ forca "o campo id dentro de incident": sem ele,
     * o Spring Data acharia o getIncidentId() do Alert, que nao e uma coluna, e a consulta quebraria.
     */
    List<Alert> findByIncident_IdOrderByTsAsc(Long incidentId);

    /** Os alertas vistos a partir de um instante (origens e alvos da visao geral). */
    List<Alert> findByTsGreaterThanEqual(Instant since);
}
