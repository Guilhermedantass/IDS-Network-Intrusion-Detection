# api/ — API do IDS

Java 25 + Spring Boot 4.1, PostgreSQL 18 + Flyway. Recebe os alertas do sensor, agrupa em incidentes e avisa o
dashboard ao vivo por WebSocket. Próxima etapa: explicações dos incidentes com a LLM.

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

## Endpoints

| | Quem usa | O que faz |
|---|---|---|
| `POST /api/alerts` | sensor | recebe um lote `{sensor, alerts: [...]}` (formato em `sensor/src/alerts.py`). 201 `{"saved": n}`; 400 se o JSON ou um campo obrigatório estiver errado |
| `GET /api/incidents?limit=50` | dashboard | os incidentes mais recentes primeiro (`limit` de 1 a 500) |
| `GET /api/incidents/{id}` | dashboard | um incidente (404 se não existe) |
| `GET /api/alerts?incident={id}` | dashboard | os alertas de um incidente, em ordem de tempo (`AlertResponse`) |
| `ws://localhost:8080/ws` (STOMP) | dashboard | tópico `/topic/incidents`: um incidente cada vez que abre ou muda |
| `GET /actuator/health` | monitoramento | `{"status": "UP"}` |

O `GET` e o WebSocket mandam o incidente no mesmo formato, sempre completo:

```json
{"id": 1, "sensor": "pc-casa", "type": "SYN Flood", "dstIp": "127.0.0.1",
 "startedAt": "2026-10-22T18:40:00Z", "lastSeenAt": "2026-10-22T18:40:20Z", "alertCount": 2, "peakRate": 180.0}
```

O dashboard busca a lista com o `GET` ao abrir e depois só troca pelo `id` o que chega no WebSocket. O navegador só
aceita conexões de `ids.dashboard-origin` (`application.yml`, padrão `http://localhost:4200`); o CORS libera só `GET`.

## Incidentes

Vários alertas do mesmo ataque viram um incidente só: mesmo **sensor + type + dstIp**, com no máximo **60 s** entre
um alerta e o seguinte (`IncidentService.GAP`, 6 janelas de 10 s do `volume.py`). Passou disso, o ataque acabou e o
próximo alerta abre um incidente novo. O incidente guarda início, último alerta, quantidade de alertas e o pico de
pacotes/s (`peakRate`, vazio se só vieram alertas do modelo).

## Como está organizado

```
src/main/java/dev/guilhermedantas/ids/
├── IdsApiApplication.java          # main
├── alert/                          # um pacote por funcionalidade
│   ├── AlertBatchRequest.java      # DTO: o JSON que chega {sensor, alerts}
│   ├── AlertRequest.java           # DTO: um alerta (com as validações)
│   ├── AlertResponse.java          # um alerta como o dashboard recebe
│   ├── Alert.java                  # entidade JPA (tabela alerts), aponta para o incidente
│   ├── AlertRepository.java        # acesso ao banco (Spring Data JPA)
│   ├── AlertService.java           # salva o lote e coloca cada alerta num incidente, numa transação
│   └── AlertController.java        # POST /api/alerts e GET /api/alerts?incident=
├── incident/
│   ├── Incident.java               # entidade JPA (tabela incidents)
│   ├── IncidentRepository.java
│   ├── IncidentService.java        # regra de agrupamento + lista dos recentes
│   ├── IncidentMessage.java        # o formato que o dashboard recebe (GET e WebSocket)
│   ├── IncidentNotifier.java       # manda para /topic/incidents depois do commit
│   └── IncidentController.java     # GET /api/incidents e /api/incidents/{id}
└── config/
    ├── WebSocketConfig.java        # STOMP em /ws, broker simples em /topic
    └── WebConfig.java              # CORS para o dashboard
src/main/resources/
├── application.yml
└── db/migration/                   # Flyway
    ├── V1__criar_alertas.sql
    └── V2__criar_incidentes.sql
compose.yaml                        # PostgreSQL de desenvolvimento
```

O caminho de uma requisição: **Controller** (HTTP, validação) → **Service** (regra) → **Repository** (banco).
Cada camada só conhece a de baixo, então dá para testar e trocar uma sem mexer nas outras.

**Mudou o banco?** Nunca edite uma migração que já rodou: crie `V3__...sql`. O Flyway guarda quais já aplicou.
