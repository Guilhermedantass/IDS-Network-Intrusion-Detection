import { blockState, blockedIps } from './block-rules';
import { Sensor } from './sensor';

function sensor(desired: string[], reported: string[] | null, prot: string[] = []): Sensor {
  return {
    name: 'teste',
    online: true,
    lastSeen: '2026-10-23T13:00:00Z',
    reported: {
      capturing: true, interface: 'lo', startedAt: null, flows: 0, attacks: 0, alertsSent: 0, interfaces: ['lo'],
      error: null, blocked: reported, protected: prot, blockError: null,
    },
    desired: { capture: true, interface: 'lo', blocked: desired },
  };
}

describe('blockState', () => {
  it('compara o pedido com o aplicado', () => {
    expect(blockState(sensor([], []), '10.0.0.5')).toBe('none');
    expect(blockState(sensor(['10.0.0.5'], []), '10.0.0.5')).toBe('blocking');
    expect(blockState(sensor(['10.0.0.5'], ['10.0.0.5']), '10.0.0.5')).toBe('blocked');
    expect(blockState(sensor([], ['10.0.0.5']), '10.0.0.5')).toBe('unblocking');
  });

  it('nao oferece bloquear o proprio PC, o gateway nem a API', () => {
    expect(blockState(sensor([], []), '127.0.0.1')).toBe('protected');
    expect(blockState(sensor([], []), '::1')).toBe('protected');
    expect(blockState(sensor([], [], ['192.168.0.1']), '192.168.0.1')).toBe('protected');
  });

  it('sensor antigo, sem bloqueio no heartbeat', () => {
    expect(blockState(sensor([], null), '10.0.0.5')).toBe('none');
  });
});

describe('blockedIps', () => {
  it('junta pedidos e aplicados, sem repetir', () => {
    expect(blockedIps(sensor(['10.0.0.9', '10.0.0.5'], ['10.0.0.5', '10.0.0.7']))).toEqual([
      '10.0.0.5', '10.0.0.7', '10.0.0.9',
    ]);
  });
});
