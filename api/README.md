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
| `GET /api/stats?hours=24` | dashboard | resumo da visão geral: totais, maior taxa, incidente mais longo, por tipo, por hora (com os tipos), top 5 origens e alvos (`hours` de 1 a 168) |
| `ws://localhost:8080/ws` (STOMP) | dashboard | tópico `/topic/incidents`: um incidente cada vez que abre ou muda |
| `POST /api/sensors/heartbeat` | sensor (`./ids servico`) | estado do sensor a cada 5 s; a resposta é o estado desejado `{capture, interface, blocked}` |
| `GET /api/sensors` | dashboard | os sensores conhecidos: online (heartbeat há até 15 s), estado e pedido |
| `PUT /api/sensors/{name}/capture` | dashboard | pede para iniciar/parar: `{"capture": true, "interface": "lo"}` |
| `PUT /api/sensors/{name}/blocked/{ip}` | dashboard | pede para bloquear o IP no firewall do sensor (400 se não for IP ou se for protegido) |
| `DELETE /api/sensors/{name}/blocked/{ip}` | dashboard | pede para desbloquear |
| `GET /actuator/health` | monitoramento | `{"status": "UP"}` |

O `GET` e o WebSocket mandam o incidente no mesmo formato, sempre completo:

```json
{"id": 1, "sensor": "pc-casa", "type": "SYN Flood", "dstIp": "127.0.0.1",
 "startedAt": "2026-10-22T18:40:00Z", "lastSeenAt": "2026-10-22T18:40:20Z", "alertCount": 2, "peakRate": 180.0}
```

O dashboard busca a lista com o `GET` ao abrir e depois só troca pelo `id` o que chega no WebSocket. O navegador só
aceita conexões de `ids.dashboard-origin` (`application.yml`, padrão `http://localhost:4200`); o CORS libera só `GET` (e `PUT`/`DELETE` em `/api/sensors/**`).

## Controle dos sensores

O sensor nunca recebe chamadas. O serviço (`./ids servico --api ...`) manda o estado a cada 5 s e recebe na resposta
o estado desejado; o dashboard só muda o desejado. Assim o sensor não abre porta nenhuma e funciona em outra máquina.
Fica em memória: se a API reiniciar, o primeiro heartbeat de cada sensor recria tudo (e o desejado vira o estado atual,
para não parar uma captura nem desfazer um bloqueio). Não há login: quem alcança a porta 8080 pode iniciar/parar
capturas e bloquear IPs.

**Bloqueio (IPS):** o desejado também tem a lista de IPs bloqueados. Quem mexe no firewall é o sensor
(`sensor/src/firewall.py`, uma tabela própria no nftables); a API só guarda o pedido. Ela recusa loopback e os IPs
que o sensor diz serem protegidos (os dele, o gateway e o da API), e o sensor confere de novo antes de aplicar.

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
├── stats/
│   ├── StatsResponse.java          # o resumo (totais, por tipo, por hora)
│   ├── StatsService.java           # as contas, agrupando em Java
│   └── StatsController.java        # GET /api/stats
├── sensor/                         # controle dos sensores (em memória; o sensor reenvia o estado a cada 5 s)
│   ├── SensorHeartbeat.java        # o que o sensor manda
│   ├── SensorCommand.java          # o estado desejado (resposta do heartbeat): captura + IPs bloqueados
│   ├── CaptureRequest.java         # corpo do PUT .../capture
│   ├── SensorView.java             # o que o dashboard vê
│   ├── SensorRegistry.java
│   └── SensorController.java
└── config/
    ├── WebSocketConfig.java        # STOMP em /ws, broker simples em /topic
    └── WebConfig.java              # CORS para o dashboard (GET; PUT/DELETE só nos sensores)
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
