/**
 * Uma cor fixa por tipo de ataque, a mesma em todos os graficos: a cor segue o tipo, nunca a posicao
 * no ranking (se um tipo some do grafico, os outros nao trocam de cor).
 *
 * Os tipos sao os que o sensor conhece (sensor/src/volume.py e o modelo de tipo de ataque). As cores sao
 * a paleta categorica de referencia, validada para daltonismo contra o fundo branco; o vermelho fica de
 * fora porque e reservado para "ataque ativo". Desconhecido (e qualquer tipo novo) fica em cinza.
 * Tres delas tem pouco contraste com o branco: por isso os graficos sempre tem legenda e tabela.
 */
export const ATTACK_TYPES: readonly { type: string; color: string }[] = [
  { type: 'SYN Flood', color: '#2a78d6' },
  { type: 'UDP Flood', color: '#eb6834' },
  { type: 'PortScan', color: '#1baf7a' },
  { type: 'DDoS', color: '#eda100' },
  { type: 'WebAttack', color: '#e87ba4' },
  { type: 'SQLInjection', color: '#008300' },
];

const OTHER_COLOR = '#8a909c';

export function typeColor(type: string): string {
  return ATTACK_TYPES.find((t) => t.type === type)?.color ?? OTHER_COLOR;
}

/** Ordem fixa para empilhar e listar: os tipos conhecidos primeiro, os outros depois, em ordem alfabetica. */
export function typeOrder(a: string, b: string): number {
  const rank = (t: string) => {
    const i = ATTACK_TYPES.findIndex((k) => k.type === t);
    return i === -1 ? ATTACK_TYPES.length : i;
  };
  return rank(a) - rank(b) || a.localeCompare(b);
}
