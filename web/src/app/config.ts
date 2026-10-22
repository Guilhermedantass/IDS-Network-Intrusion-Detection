// Enderecos da API (api/). O dashboard precisa rodar em http://localhost:4200 (ng serve):
// e a unica origem que a API aceita (ids.dashboard-origin no application.yml).
export const API_URL = 'http://localhost:8080';
export const WS_URL = 'ws://localhost:8080/ws';

// Mesmo valor do IncidentService.GAP na API: sem alerta por mais que isso, o ataque acabou.
export const INCIDENT_GAP_MS = 60_000;
