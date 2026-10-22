package dev.guilhermedantas.ids.alert;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * Entidade JPA da tabela "alerts" (criada pelo Flyway em
 * src/main/resources/db/migration/V1__criar_alertas.sql).
 *
 * Por que separar Alert (entidade) de AlertRequest (DTO)? O DTO e o formato da API (o que entra
 * pela rede); a entidade e o formato do banco. Assim um muda sem quebrar o outro.
 * O ddl-auto: validate do application.yml faz a API nem subir se a entidade nao bater com a tabela.
 */
@Entity
@Table(name = "alerts")
public class Alert {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)   // a coluna e BIGSERIAL: o banco gera o id
    private Long id;

    private String sensor;
    private Instant ts;

    @Column(insertable = false, updatable = false)        // o banco preenche (DEFAULT now())
    private Instant receivedAt;

    private String type;
    private String detectedBy;
    private String srcIp;
    private String dstIp;
    private Integer dstPort;
    private String protocol;
    private Integer flows;
    private Integer packets;
    private Double rate;
    private Integer ports;
    private Integer sources;
    private Double probability;

    protected Alert() {   // exigido pelo JPA
    }

    static Alert from(String sensor, AlertRequest req) {
        Alert a = new Alert();
        a.sensor = sensor;
        a.ts = req.ts();
        a.type = req.type();
        a.detectedBy = req.detectedBy();
        a.srcIp = req.srcIp();
        a.dstIp = req.dstIp();
        a.dstPort = req.dstPort();
        a.protocol = req.protocol();
        a.flows = req.flows();
        a.packets = req.packets();
        a.rate = req.rate();
        a.ports = req.ports();
        a.sources = req.sources();
        a.probability = req.probability();
        return a;
    }
}
