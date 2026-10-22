# CLAUDE.md

IDS (deteccao de intrusao) com ML treinado no CIC-IDS-2017. Projeto de estudo/portfolio (LinkedIn).
Responda em **portugues**, com linguagem simples.

## Estado atual
Python em `sensor/` (o `.venv` fica na raiz; `./ids` usa `PYTHONPATH=sensor`):
- `src/data.py` limpeza + colunas removidas (atalhos, flags TCP) · `src/features.py` selecao (SHAP/correlacao)
- `src/pipeline.py` `IDSPipeline`: modelo binario (BENIGN x ataque) -> modelo de tipo (DDoS/PortScan/WebAttack/SQLInjection/Desconhecido)
- `src/flows.py` pacotes -> fluxos · `src/volume.py` deteccao por volume (janela de 10 s, limites em `Limits`) · `src/live.py` captura com tcpdump · `src/detect.py` classifica e grava · `src/storage.py` SQLite · `src/report.py` resumo · `src/ids.py` CLI
- `sensor/notebooks/02..05` treino (gerados e executados); `notebook_*.ipynb` e `archive/` sao historico
- `sensor/results/modelos/*.ubj|*.json` modelos versionados no git; `sensor/datas/raw/` CSVs (fora do git)

## Comandos
```bash
./ids ao-vivo [-i lo]        # captura ao vivo (sudo); trafego para o proprio PC passa pela interface lo
./ids teste-nmap [--syn]     # escaneia 127.0.0.1 e mostra se detectou
./ids teste-flood [--udp]    # flood em 127.0.0.1:9 (taxa limitada) e mostra se detectou
./ids arquivo X.pcap | ./ids resumo [--lista]
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
`api/` (Java 21 + Spring Boot 3, PostgreSQL + Flyway, incidentes, WebSocket STOMP, Spring AI + Ollama) ->
`web/` (Angular 22, dashboard/ao vivo/incidentes/controle do sensor) -> `docker compose` (instalavel; captura
ao vivo so em host Linux). Ordem: sensor -> API -> Angular -> LLM -> Docker.
