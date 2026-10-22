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
  };
  desired: SensorCommand;
}

/** O pedido do dashboard (PUT /api/sensors/{name}/capture). interface null = a padrao do sensor. */
export interface SensorCommand {
  capture: boolean;
  interface: string | null;
}
