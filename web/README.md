# web/ — dashboard do IDS

Angular 22 (standalone, signals, sem zone.js). Mostra os incidentes ao vivo: busca a lista na API
(`GET /api/incidents`) e acompanha as mudanças pelo WebSocket (`/topic/incidents`).

## Rodando

Precisa do Node 24 e da API de pé (`cd api && ./mvnw spring-boot:run`).

```bash
cd web
npm install          # só na primeira vez
npm start            # http://localhost:4200 (precisa ser essa porta: é a única origem que a API aceita)
npm test             # testes (Vitest)
```

Para ter incidentes na tela: `./ids teste-flood --api http://localhost:8080` (na raiz do projeto, em outro terminal).

## Como está organizado

```
src/app/
├── config.ts                    # endereços da API e o GAP de 60 s (mesmo valor da API)
├── clock.ts                     # relógio de 1 s compartilhado (status ativo/encerrado)
├── app.ts / app.html / app.scss # casca: barra lateral + <router-outlet>; liga o WebSocket ao abrir
├── app.routes.ts                # /overview (inicial), /incidents, /incidents/:id e /sensors
├── shell/sidebar.*              # barra lateral: navegação e status da conexão com a API
├── overview/                    # visão geral (página inicial): manchete, números, gráficos e rankings das últimas 24 h
│   ├── stats.ts                 # o formato do resumo (espelha o StatsResponse do Java)
│   └── overview.*
├── sensors/                     # iniciar/parar a captura de cada sensor (busca a lista a cada 3 s)
│   ├── sensor.ts                # o formato (espelha o SensorView do Java)
│   ├── sensor-api.ts            # as chamadas de /api/sensors (captura, bloquear, desbloquear)
│   ├── block-rules.ts           # estado do bloqueio de um IP (pedido x aplicado), com testes
│   └── sensors.*
└── incidents/
    ├── incident.ts              # o formato do incidente (espelha o IncidentMessage do Java)
    ├── incident-alert.ts        # o formato de um alerta (espelha o AlertResponse do Java)
    ├── attack-types.ts          # cor fixa por tipo de ataque
    ├── incident-rules.ts        # funções puras: upsertIncident, isActive, formatDuration
    ├── incident-rules.spec.ts   # os testes delas
    ├── incident-store.ts        # estado (signals) + GET + WebSocket
    ├── incident-list.*          # a lista
    └── incident-detail.*        # um incidente e os alertas dele
```

Quem guarda o estado é o **store**; a tela só lê os signals dele. As regras (como juntar um incidente na lista,
quando ele está ativo) ficam em funções puras, sem Angular, para dar para testar sozinhas.

## Visual

Tema claro, IBM Plex Sans (e Plex Mono só nos IPs). Cores e fontes são variáveis em `src/styles.scss`: um tema escuro
depois é só redefinir essas variáveis. O vermelho (`--signal`) aparece só em ataque ativo. Nos gráficos, cada tipo de ataque tem uma cor fixa
(`incidents/attack-types.ts`, paleta validada para daltonismo), sempre com legenda e versão em tabela.
Números e datas no formato brasileiro (`LOCALE_ID` pt-BR no `app.config.ts`).

## Testando ao vivo

Para controlar a captura pelo dashboard (página Sensores), ligue o serviço do sensor na raiz do projeto; ele pede a
senha do sudo uma vez:

```bash
./ids servico --api http://localhost:8080
```

Ou gere um ataque direto, sem o serviço (na raiz do projeto):

```bash
./ids teste-flood --segundos 3600 --taxa 300 --api http://localhost:8080   # Ctrl+C para parar
```

O incidente aparece como ativo, ganha um alerta a cada 30 s enquanto o ataque continua e vira encerrado 60 s depois
do último alerta.
