import { Incident } from './incident';
import { isActive, upsertIncident } from './incident-rules';

function incident(id: number, lastSeenAt: string, alertCount = 1): Incident {
  return {
    id,
    sensor: 'teste',
    type: 'SYN Flood',
    dstIp: '10.0.0.' + id,
    startedAt: lastSeenAt,
    lastSeenAt,
    alertCount,
    peakRate: 100,
  };
}

describe('upsertIncident', () => {
  it('adiciona um incidente novo', () => {
    const result = upsertIncident([], incident(1, '2026-10-22T13:00:00Z'));
    expect(result.map((i) => i.id)).toEqual([1]);
  });

  it('troca o incidente com o mesmo id pelo estado novo', () => {
    const list = [incident(1, '2026-10-22T13:00:00Z', 1)];
    const result = upsertIncident(list, incident(1, '2026-10-22T13:00:20Z', 3));
    expect(result).toHaveLength(1);
    expect(result[0].alertCount).toBe(3);
  });

  it('deixa o mais recente primeiro', () => {
    const list = [incident(2, '2026-10-22T13:05:00Z'), incident(1, '2026-10-22T13:00:00Z')];
    // o 1 recebeu um alerta agora: sobe para o topo
    const result = upsertIncident(list, incident(1, '2026-10-22T13:10:00Z'));
    expect(result.map((i) => i.id)).toEqual([1, 2]);
  });

  it('nao altera a lista recebida', () => {
    const list = [incident(1, '2026-10-22T13:00:00Z')];
    const copia = structuredClone(list);
    const result = upsertIncident(list, incident(2, '2026-10-22T13:05:00Z'));
    expect(list).toEqual(copia);
    expect(result).not.toBe(list);
  });
});

describe('isActive', () => {
  const ultimoAlerta = incident(1, '2026-10-22T13:00:00Z');

  it('ativo ate 60 s depois do ultimo alerta', () => {
    expect(isActive(ultimoAlerta, Date.parse('2026-10-22T13:00:00Z'))).toBe(true);
    expect(isActive(ultimoAlerta, Date.parse('2026-10-22T13:01:00Z'))).toBe(true);
  });

  it('encerrado depois disso', () => {
    expect(isActive(ultimoAlerta, Date.parse('2026-10-22T13:01:01Z'))).toBe(false);
  });
});
