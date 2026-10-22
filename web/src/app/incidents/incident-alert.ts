/**
 * Um alerta de um incidente, como a API manda em GET /api/alerts?incident=ID.
 * Espelha o record AlertResponse do Java: mudou la, muda aqui.
 * Os campos que nao se aplicam vem null: flows e probability so no modelo; packets, rate e sources so no volume.
 */
export interface IncidentAlert {
  id: number;
  ts: string;                 // quando o sensor viu
  receivedAt: string;         // quando a API recebeu
  type: string;
  detectedBy: string;         // 'volume' ou 'modelo'
  srcIp: string | null;       // null no DDoS (muitas origens)
  dstIp: string;
  dstPort: number | null;
  protocol: string;
  flows: number | null;
  packets: number | null;
  rate: number | null;        // pacotes/s
  ports: number | null;
  sources: number | null;
  probability: number | null; // confianca do modelo, de 0 a 1
}
