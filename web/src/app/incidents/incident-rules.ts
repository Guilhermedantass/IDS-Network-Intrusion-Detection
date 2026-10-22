import { INCIDENT_GAP_MS } from '../config';
import { Incident } from './incident';

/**
 * Coloca um incidente que chegou (do WebSocket) na lista: troca o de mesmo id ou adiciona,
 * e devolve uma lista NOVA ordenada pelo lastSeenAt, mais recente primeiro.
 *
 * Por que lista nova? Um signal so avisa a tela quando o valor muda de referencia (compara com ===).
 * Se o mesmo array fosse alterado, para o signal "nada mudou" e a tela nao atualizaria.
 */
export function upsertIncident(list: readonly Incident[], incoming: Incident): Incident[] {
  return [...list.filter((i) => i.id !== incoming.id), incoming]
    .sort((a, b) => Date.parse(b.lastSeenAt) - Date.parse(a.lastSeenAt));
}

/**
 * true se o ultimo alerta foi ha no maximo INCIDENT_GAP_MS de nowMs. Mesma regra da API: passou do GAP
 * sem alerta, o ataque acabou. O incidente nao muda no banco quando acaba (nao chega nada pelo WebSocket),
 * por isso a tela calcula o status com o relogio. Recebe nowMs para dar para testar com um horario fixo.
 */
export function isActive(incident: Incident, nowMs: number): boolean {
  return nowMs - Date.parse(incident.lastSeenAt) <= INCIDENT_GAP_MS;
}

/** Duracao legivel: '45 s', '2 min 05 s', '1 h 03 min'. */
export function formatDuration(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  const h = Math.floor(total / 3600);
  const min = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  if (h > 0) {
    return `${h} h ${pad(min)} min`;
  }
  if (min > 0) {
    return `${min} min ${pad(s)} s`;
  }
  return `${s} s`;
}
