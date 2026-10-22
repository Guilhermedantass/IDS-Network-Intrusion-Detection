package dev.guilhermedantas.ids.incident;

import java.util.List;
import java.util.Optional;

import org.springframework.data.domain.Limit;
import org.springframework.data.jpa.repository.JpaRepository;

public interface IncidentRepository extends JpaRepository<Incident, Long> {

    /** O incidente mais recente do mesmo ataque (o Spring Data monta a consulta pelo nome do metodo). */
    Optional<Incident> findFirstBySensorAndTypeAndDstIpOrderByLastSeenAtDesc(String sensor, String type, String dstIp);

    /** Os incidentes mais recentes primeiro; o Limit vira o LIMIT do SQL. */
    List<Incident> findAllByOrderByLastSeenAtDesc(Limit limit);
}
