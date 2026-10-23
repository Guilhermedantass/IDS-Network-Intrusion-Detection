/**
 * Um sensor como a API manda em GET /api/sensors. Espelha o record SensorView do Java.
 * reported = o que o sensor disse no ultimo heartbeat; desired = o que foi pedido para ele.
 * Os dois diferentes = o sensor ainda vai aplicar (no proximo heartbeat, em ate 5 s).
 */
export interface Sensor {
  name: string;
  online: boolean;
  lastSeen: string;
  reported: {
    capturing: boolean;
    interface: string | null;
    startedAt: string | null;
    flows: number;
    attacks: number;
    alertsSent: number;
    interfaces: string[];
    error: string | null;
    blocked: string[] | null;      // IPs bloqueados de fato no firewall (null = sensor antigo, sem bloqueio)
    protected: string[] | null;    // IPs que o sensor nunca bloqueia: os dele, o gateway e o da API
    blockError: string | null;     // por que um pedido de bloqueio nao foi aplicado
  };
  desired: SensorCommand;
}

/** O estado desejado (record SensorCommand do Java). */
export interface SensorCommand {
  capture: boolean;
  interface: string | null;
  blocked: string[];
}

/** O pedido de iniciar/parar (PUT /api/sensors/{name}/capture). interface null = a padrao do sensor. */
export interface CaptureRequest {
  capture: boolean;
  interface: string | null;
}
