/**
 * Um incidente, como a API manda no GET /api/incidents e no topico /topic/incidents (WebSocket).
 * Espelha o record IncidentMessage do Java: mudou la, muda aqui.
 *
 * Sempre o estado completo: quando chega um incidente que ja esta na lista (mesmo id), ele substitui o antigo.
 * Datas chegam como texto ISO ("2026-10-22T18:40:00Z"); para comparar, use Date.parse(...).
 */
export interface Incident {
  id: number;
  sensor: string;
  type: string;            // SYN Flood, UDP Flood, PortScan, DDoS...
  dstIp: string;
  startedAt: string;
  lastSeenAt: string;
  alertCount: number;
  peakRate: number | null; // pacotes/s; null quando so vieram alertas do modelo
}
