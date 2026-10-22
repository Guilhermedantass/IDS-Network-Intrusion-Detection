# api/ — API do IDS

Java 25 + Spring Boot 4.1, PostgreSQL 18 + Flyway. Recebe os alertas do sensor (`POST /api/alerts`) e, nas
próximas etapas, agrupa os alertas em incidentes, avisa o dashboard por WebSocket e gera explicações com a LLM.

## Rodando

Precisa do JDK 25 e do Docker (o Maven não: o `./mvnw` baixa sozinho na primeira vez).

```bash
sudo apt install openjdk-25-jdk docker.io docker-compose-v2
sudo usermod -aG docker $USER     # usar o docker sem sudo; vale depois de sair e entrar de novo na sessão
```

```bash
cd api
./mvnw spring-boot:run            # sobe o PostgreSQL do compose.yaml sozinho e a API em localhost:8080
./mvnw test                       # testes (sobem um PostgreSQL descartável com Testcontainers)
curl localhost:8080/actuator/health
```

Para o sensor mandar os alertas: `./ids teste-flood --api http://localhost:8080` (na raiz do projeto).

## Como está organizado

```
src/main/java/dev/guilhermedantas/ids/
├── IdsApiApplication.java      # main
└── alert/                      # um pacote por funcionalidade (alertas, depois incidentes...)
    ├── AlertBatchRequest.java  # DTO: o JSON que chega {sensor, alerts}
    ├── AlertRequest.java       # DTO: um alerta
    ├── Alert.java              # entidade JPA (tabela alerts)
    ├── AlertRepository.java    # acesso ao banco (Spring Data JPA)
    ├── AlertService.java       # regras de negócio
    └── AlertController.java    # endpoint HTTP
src/main/resources/
├── application.yml
└── db/migration/V1__criar_alertas.sql   # Flyway: cria a tabela alerts
compose.yaml                             # PostgreSQL de desenvolvimento
```

O caminho de uma requisição: **Controller** (HTTP, validação) → **Service** (regra) → **Repository** (banco).
Cada camada só conhece a de baixo, então dá para testar e trocar uma sem mexer nas outras.

## Roteiro da etapa 1: receber alertas

Cada arquivo de `alert/` tem um TODO explicando o que fazer. Uma ordem que funciona:

1. **`AlertRequest` e `AlertBatchRequest`** (records): o formato do JSON. Record é uma classe imutável que já vem
   com construtor, getters, `equals` e `toString`, ideal para DTO.
2. **`Alert`** (entidade): o formato do banco. Rode a API: se algum campo não bater com a tabela, ela nem sobe
   (`ddl-auto: validate`) e a mensagem diz qual coluna está errada.
3. **`AlertRepository`**: uma linha.
4. **`AlertService`**: converte e salva, com `@Transactional`.
5. **`AlertController`**: o `@PostMapping`. Teste com o `curl` que está no TODO e depois com o sensor.
6. **Teste automatizado** em `src/test/.../alert/`: um `@SpringBootTest` com `MockMvc` mandando um JSON válido
   (espera 201 e uma linha no banco) e um inválido (espera 400). O `TestcontainersConfiguration` já sobe o banco.

Quando estiver pronto, me chame para revisar. Depois vêm os **incidentes** (vários alertas do mesmo ataque viram um
incidente só, com início, fim e pico) e o **WebSocket** para o dashboard ao vivo.

**Mudou o banco?** Nunca edite uma migração que já rodou: crie `V2__...sql`. O Flyway guarda quais já aplicou.
