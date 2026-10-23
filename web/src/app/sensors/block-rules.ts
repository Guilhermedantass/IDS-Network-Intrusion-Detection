import { Sensor } from './sensor';

/**
 * Em que pe esta o bloqueio de um IP num sensor, comparando o pedido (desired) com o aplicado (reported):
 *   none        nao bloqueado            blocking    pedido, o sensor ainda vai aplicar
 *   blocked     bloqueado no firewall    unblocking  desbloqueio pedido, ainda nao aplicado
 *   protected   nunca pode ser bloqueado (o proprio PC, o gateway ou a API)
 */
export type BlockState = 'none' | 'blocking' | 'blocked' | 'unblocking' | 'protected';

export function blockState(sensor: Sensor, ip: string): BlockState {
  const wanted = sensor.desired.blocked.includes(ip);
  const applied = sensor.reported.blocked?.includes(ip) ?? false;
  if (wanted) {
    return applied ? 'blocked' : 'blocking';
  }
  if (applied) {
    return 'unblocking';
  }
  return isProtected(sensor, ip) ? 'protected' : 'none';
}

function isProtected(sensor: Sensor, ip: string): boolean {
  return ip.startsWith('127.') || ip === '::1' || (sensor.reported.protected?.includes(ip) ?? false);
}

/** Os IPs que aparecem na tela do sensor: os bloqueados e os que ainda estao a caminho (pedidos ou saindo). */
export function blockedIps(sensor: Sensor): string[] {
  return [...new Set([...sensor.desired.blocked, ...(sensor.reported.blocked ?? [])])].sort();
}
