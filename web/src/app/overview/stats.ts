/**
 * Resumo das ultimas horas, como a API manda em GET /api/stats?hours=24.
 * Espelha o record StatsResponse do Java: mudou la, muda aqui.
 */
export interface Stats {
  since: string;                                   // comeco da hora mais antiga da janela
  incidents: number;                               // incidentes que comecaram na janela
  alerts: number;                                  // alertas vistos na janela
  highestRate: Highlight | null;                   // maior pico de pacotes/s
  longest: Highlight | null;                       // incidente mais longo; value em segundos
  byType: { type: string; incidents: number }[];   // do mais comum ao menos
  byHour: HourCount[];                             // uma entrada por hora, inclusive as zeradas
  topSources: IpCount[];                           // origens com mais alertas (ate 5)
  topTargets: IpCount[];                           // destinos com mais alertas (ate 5)
}

export interface Highlight {
  incidentId: number;
  type: string;
  value: number;
}

export interface HourCount {
  hour: string;
  incidents: number;
  byType: Record<string, number>;                  // so os tipos que tiveram incidente na hora
}

export interface IpCount {
  ip: string;
  incidents: number;
  alerts: number;
}
