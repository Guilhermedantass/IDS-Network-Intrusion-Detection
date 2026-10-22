package dev.guilhermedantas.ids.alert;

/**
 * Entidade JPA da tabela "alerts" (criada pelo Flyway em
 * src/main/resources/db/migration/V1__criar_alertas.sql).
 *
 * TODO:
 *   - anotar com @Entity e @Table(name = "alerts")
 *   - id: Long com @Id e @GeneratedValue(strategy = GenerationType.IDENTITY) (a coluna e BIGSERIAL)
 *   - um campo para cada coluna; nomes em camelCase viram snake_case sozinhos (dstIp -> dst_ip)
 *   - "type" e palavra comum em SQL, mas aqui funciona; se quiser, use @Column(name = "type")
 *   - receivedAt: o banco preenche (DEFAULT now()); marque com
 *     @Column(insertable = false, updatable = false) para o Hibernate nao mandar null
 *   - JPA exige um construtor sem argumentos (pode ser protected)
 *   - crie um metodo estatico "from(String sensor, AlertRequest req)" que copia os campos do DTO
 *
 * Por que separar Alert (entidade) de AlertRequest (DTO)? O DTO e o formato da API (o que entra
 * pela rede); a entidade e o formato do banco. Assim um muda sem quebrar o outro.
 * O ddl-auto: validate do application.yml faz a API nem subir se a entidade nao bater com a tabela.
 */
public class Alert {
}
