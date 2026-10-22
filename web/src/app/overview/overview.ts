import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Clock } from '../clock';
import { API_URL } from '../config';
import { typeColor, typeOrder } from '../incidents/attack-types';
import { formatDuration, isActive } from '../incidents/incident-rules';
import { IncidentStore } from '../incidents/incident-store';
import { HourCount, Stats } from './stats';

const HOURS = 24;
const RECENT = 5;

/**
 * Visao geral das ultimas 24 horas (rota 'overview', a pagina inicial).
 *
 * O que e ao vivo vem do store (WebSocket): ataques agora, ultimo alerta, incidentes recentes.
 * O resto vem do resumo da API (GET /api/stats), buscado de novo quando um incidente muda ou vira a hora.
 * Os graficos sao HTML/CSS puro: cada barra e um elemento com altura (ou largura) em % do maior valor.
 */
@Component({
  selector: 'app-overview',
  imports: [DatePipe, DecimalPipe, RouterLink],
  templateUrl: './overview.html',
  styleUrl: './overview.scss',
})
export class Overview {
  private readonly http = inject(HttpClient);
  private readonly store = inject(IncidentStore);
  protected readonly now = inject(Clock).now;

  protected readonly hours = HOURS;
  protected readonly stats = signal<Stats | null>(null);
  protected readonly failed = signal(false);

  protected readonly typeColor = typeColor;
  protected readonly isActive = isActive;
  protected readonly formatDuration = formatDuration;

  // ---- ao vivo (store)

  protected readonly activeCount = computed(
    () => this.store.incidents().filter((i) => isActive(i, this.now())).length,
  );
  protected readonly recent = computed(() => this.store.incidents().slice(0, RECENT));

  /** Ha quanto tempo chegou o ultimo alerta de qualquer incidente (null se nao ha nenhum). */
  protected readonly sinceLastAlert = computed(() => {
    const last = this.store.incidents()[0];   // a lista ja vem do mais recente para o mais antigo
    return last ? formatDuration(this.now() - Date.parse(last.lastSeenAt)) : null;
  });

  // ---- resumo (API)

  /** Os tipos que aparecem na janela, na ordem fixa (a mesma da pilha e da legenda). */
  protected readonly types = computed(() =>
    (this.stats()?.byType ?? []).map((t) => t.type).sort(typeOrder),
  );
  protected readonly maxPerHour = computed(() => Math.max(1, ...(this.stats()?.byHour.map((h) => h.incidents) ?? [])));
  protected readonly maxPerType = computed(() => Math.max(1, ...(this.stats()?.byType.map((t) => t.incidents) ?? [])));

  /** A hora com mais incidentes (a mais recente, se empatar): o unico total escrito no grafico. */
  protected readonly peakHour = computed(() => {
    const byHour = this.stats()?.byHour ?? [];
    let peak = -1;
    byHour.forEach((h, i) => {
      if (h.incidents > 0 && h.incidents >= (byHour[peak]?.incidents ?? 0)) {
        peak = i;
      }
    });
    return peak;
  });

  /** Muda so quando vira a hora: a janela de 24 h anda junto. */
  private readonly currentHour = computed(() => Math.floor(this.now() / 3_600_000));

  constructor() {
    effect((onCleanup) => {
      this.store.incidents();
      this.currentHour();
      const sub = this.http.get<Stats>(`${API_URL}/api/stats`, { params: { hours: HOURS } }).subscribe({
        next: (stats) => {
          this.stats.set(stats);
          this.failed.set(false);
        },
        error: () => this.failed.set(true),
      });
      onCleanup(() => sub.unsubscribe());
    });
  }

  /** Os pedacos de uma coluna, de baixo para cima, na ordem fixa dos tipos. */
  protected segments(h: HourCount): { type: string; count: number }[] {
    return this.types()
      .filter((t) => h.byType[t])
      .map((t) => ({ type: t, count: h.byType[t] }));
  }

  protected plural(n: number, one: string, many: string): string {
    return `${n} ${n === 1 ? one : many}`;
  }
}
