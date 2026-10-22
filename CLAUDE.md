# CLAUDE.md

IDS (deteccao de intrusao) com ML treinado no CIC-IDS-2017. Projeto de estudo/portfolio (LinkedIn).
Responda em **portugues**, com linguagem simples.

## Estado atual
Python em `sensor/` (o `.venv` fica na raiz; `./ids` usa `PYTHONPATH=sensor`):
- `src/data.py` limpeza + colunas removidas (atalhos, flags TCP) · `src/features.py` selecao (SHAP/correlacao)
- `src/pipeline.py` `IDSPipeline`: modelo binario (BENIGN x ataque) -> modelo de tipo (DDoS/PortScan/WebAttack/SQLInjection/Desconhecido)
- `src/flows.py` pacotes -> fluxos · `src/volume.py` deteccao por volume (janela de 10 s, limites em `Limits`) · `src/alerts.py` alertas no formato da API + envio HTTP em thread · `src/live.py` captura com tcpdump · `src/service.py` servico controlado pelo dashboard (heartbeat) · `src/detect.py` classifica e grava · `src/storage.py` SQLite · `src/report.py` resumo · `src/ids.py` CLI
- `sensor/notebooks/02..05` treino (gerados e executados); `notebook_*.ipynb` e `archive/` sao historico
- `sensor/results/modelos/*.ubj|*.json` modelos versionados no git; `sensor/datas/raw/` CSVs (fora do git)

`api/` (Java 25 + Spring Boot 4.1.1, pacote `dev.guilhermedantas.ids`, Maven via `./mvnw`; detalhes em `api/README.md`):
- `alert/` `POST /api/alerts`: valida, salva em `alerts` e coloca cada alerta num incidente, tudo numa transacao
- `incident/` incidente = mesmo sensor + type + dstIp com ate 60 s (`IncidentService.GAP`) entre alertas;
  `GET /api/incidents?limit=`, `/api/incidents/{id}`, `GET /api/alerts?incident=`, `GET /api/stats?hours=` (`stats/`); WebSocket STOMP em `/ws`, topico `/topic/incidents`
  (`IncidentMessage`, sempre o estado completo; sai so depois do commit via `@TransactionalEventListener`)
- `sensor/` controle dos sensores em memoria (`SensorRegistry`): `POST /api/sensors/heartbeat` (sensor manda o estado
  a cada 5 s e recebe o desejado), `GET /api/sensors`, `PUT /api/sensors/{name}/capture`; offline apos 15 s
- `config/` WebSocket + CORS (GET; PUT so em `/api/sensors/**`); unica origem aceita: `ids.dashboard-origin` no `application.yml` (localhost:4200)
- Migracoes Flyway em `db/migration/` (V1 alerts, V2 incidents + `alerts.incident_id`); nunca editar uma que ja rodou
- Postgres de dev no `api/compose.yaml` (sobe sozinho com spring-boot-docker-compose); testes com Testcontainers

`web/` (Angular 22 standalone + signals, sem zone.js, Vitest, `@stomp/stompjs`; detalhes em `web/README.md`):
- `/overview` (pagina inicial: manchete ao vivo, totais, graficos por hora/tipo, top origens/alvos das ultimas 24 h), `/incidents` ao vivo (GET + WebSocket, status ativo/encerrado pelo `Clock`) `/incidents/:id` com os alertas e `/sensors` (iniciar/parar captura);
  WebSocket ligado no `App`; barra lateral em `shell/`
- visual: tema claro, IBM Plex Sans/Mono, tokens em `styles.scss`; vermelho (`--signal`) so para ataque ativo;
  cor fixa por tipo de ataque em `incidents/attack-types.ts`; `LOCALE_ID` pt-BR
- precisa rodar em localhost:4200 (origem aceita pela API)

## Comandos
```bash
./ids ao-vivo [-i lo]        # captura ao vivo (sudo); trafego para o proprio PC passa pela interface lo
./ids teste-nmap [--syn]     # escaneia 127.0.0.1 e mostra se detectou
./ids teste-flood [--udp]    # flood em 127.0.0.1:9 (taxa limitada) e mostra se detectou
./ids arquivo X.pcap | ./ids resumo [--lista]
./ids <comando> --api http://localhost:8080 [--sensor NOME]   # tambem envia alertas (ou IDS_API_URL/IDS_SENSOR)
./ids servico --api http://localhost:8080   # fica ligado; captura controlada pelo dashboard (sudo uma vez ao ligar)
cd sensor && ../.venv/bin/python -m pytest   # testes
# Retreino: executar notebooks 02, 03, 04, 05 nessa ordem (de dentro de sensor/notebooks/)
```

## Regras importantes (nao quebrar)
- `sensor/src/flows.py` reproduz o CICFlowMeter em Java **com os bugs dele**, conferidos contra os CSVs: tempos em us,
  padding Ethernet conta como payload, primeiro pacote contado 2x em Packet Length Mean/Std/Variance e
  Average Packet Size, `act_data_pkt_fwd` ignora o primeiro pacote e o padding, fim do fluxo no FIN ou em 120 s.
  Qualquer mudanca deve ser validada contra os CSVs. Nao usar o pacote `cicflowmeter` do PyPI (escala errada).
- Flags TCP do CIC-IDS-2017 estao erradas: ficam fora dos modelos (`FLAG_COLUMNS` em `sensor/src/data.py`).
- O extrator precisa gerar todas as features candidatas (o retreino pode escolher qualquer uma).
- Contratos com a API: `POST /api/alerts` `{sensor, alerts: [...]}` (docstring de `src/alerts.py`) e o heartbeat
  (docstring de `src/service.py`), campos camelCase. Mudou o formato? Avisar o usuario: a API em Java depende dele.
- Modelos olham um fluxo por vez; floods ficam com `src/volume.py` (conta so SYN sem ACK e UDP, nao respostas).
  Cada fluxo tem um tipo so: ataque de volume ativo vence o modelo (`detected_by`, `model_type` na tabela flows).

## Codigo
- Comentarios e mensagens em portugues **sem acentos** no Python; nomes de funcoes em ingles; seguir o estilo do arquivo.
- README e docs com acentos normais.

## Forma de trabalho
- **Modo misto:** eu faco o Python e a infraestrutura (Docker, configs, esqueletos). No Java/Angular, o usuario
  implementa as funcionalidades principais: dar estrutura, explicar conceitos, deixar TODOs e revisar o codigo dele.
- Commit so quando o usuario pedir; push so quando pedir. Mensagens de commit em portugues (`feat:`, `fix:`).
- Dois PCs: notebook do trabalho (sem GPU, 14 GB RAM, pouco disco) e PC de casa (GTX 1070, 8 GB VRAM, 24 GB RAM).
  O modelo da LLM deve ser configuravel (~3B no notebook, 7-8B em casa).

## Proximos passos (arquitetura planejada)
`sensor/` (Python: captura, ML, deteccao por volume, envia alertas por HTTP, API de controle) ->
`api/` (Java 25 + Spring Boot 4.1, PostgreSQL + Flyway, incidentes, WebSocket STOMP, Spring AI + Ollama) ->
`web/` (Angular 22, dashboard/ao vivo/incidentes/controle do sensor) -> `docker compose` (instalavel; captura
ao vivo so em host Linux). Ordem: sensor -> API -> Angular -> LLM -> Docker.
Feito: sensor, API, Angular (visao geral, incidentes, detalhe, sensores). Falta: LLM e Docker.
Decidido: NAO expor no alerta/dashboard se o modelo de ML tambem detectou (fica `detectedBy: volume`).
Na pratica, o usuario tem pedido que eu escreva o Java/Angular e explique cada parte (perguntar se mudar).

## Plano para publicar no LinkedIn (combinado em 2026-10-22, nada comecado)
O usuario achou o projeto "pobre" para postar. Conclusao: o projeto ja e acima da media (captura real, extrator
do CICFlowMeter com os bugs, flags TCP erradas no dataset, deteccao por volume cobrindo o ponto cego do modelo,
sistema ponta a ponta com testes); falta demo e gancho. Proposta, por ordem:
1. **Detectar e responder (IPS):** botao "Bloquear origem" no incidente criando regra no `nftables` (e modo
   automatico opcional), com lista de excecoes (nunca bloquear o proprio PC/gateway) e desbloqueio pelo dashboard.
2. **MITRE ATT&CK por incidente:** PortScan -> T1046, floods/DDoS -> T1498 (conferir os IDs e subtecnicas antes).
3. **LLM explicando cada incidente** (o que e, risco, o que fazer), usando o MITRE; Spring AI + Ollama, modelo
   configuravel (~3B no notebook, 7-8B em casa).
4. **Demo com ataque de outra maquina:** VM Kali atacando o PC pela rede (sensor sem `-i lo`), video de ~30 s:
   ataque -> incidente ativo com MITRE -> explicacao da LLM -> bloqueio -> ataque para.
5. Vitrine: README da raiz reescrito (prints/GIF no topo, diagrama, metricas REAIS de
   `sensor/results/modelos/*.json`, decisoes tecnicas, limitacoes), `docker compose up` (banco + API + dashboard;
   sensor analisando um pcap de exemplo), CI no GitHub Actions (testes das 3 partes + selo), LICENSE (MIT?).
6. Opcional: aviso no Telegram/Discord quando um incidente abre.
O texto do post e do usuario, na voz dele; ajudar so com estrutura e revisao.
Em aberto: (a) se da para rodar VM (VirtualBox/KVM) no notebook ou no PC de casa; (b) se o usuario quer o
bloqueio automatico ou so o botao manual.
