import { DatePipe, DecimalPipe, PercentPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, input, numberAttribute, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Clock } from '../clock';
import { Incident } from './incident';
import { IncidentAlert } from './incident-alert';
import { formatDuration, isActive } from './incident-rules';
import { IncidentStore } from './incident-store';

/**
 * Um incidente e os alertas dele (rota 'incidents/:id').
 *
 * O incidente vem do store quando esta na lista (e ai se atualiza ao vivo pelo WebSocket);
 * se for antigo, busca pelo id. Os alertas sao buscados de novo sempre que o incidente ganha um alerta.
 */
@Component({
  selector: 'app-incident-detail',
  imports: [DatePipe, DecimalPipe, PercentPipe, RouterLink],
  templateUrl: './incident-detail.html',
  styleUrl: './incident-detail.scss',
})
export class IncidentDetail {
  private readonly store = inject(IncidentStore);
  protected readonly now = inject(Clock).now;

  /** O :id da rota (withComponentInputBinding no app.config). */
  readonly id = input.required({ transform: numberAttribute });

  private readonly fetched = signal<Incident | null>(null);
  protected readonly notFound = signal(false);
  protected readonly alerts = signal<IncidentAlert[] | null>(null);   // null = carregando

  protected readonly incident = computed(
    () => this.store.incidents().find((i) => i.id === this.id()) ?? this.fetched(),
  );
  protected readonly active = computed(() => {
    const i = this.incident();
    return i !== null && isActive(i, this.now());
  });
  protected readonly duration = computed(() => {
    const i = this.incident();
    return i ? formatDuration(Date.parse(i.lastSeenAt) - Date.parse(i.startedAt)) : '';
  });

  /** So o numero de alertas: um computed so avisa quando o valor muda, nao a cada tique do relogio. */
  private readonly alertCount = computed(() => this.incident()?.alertCount);

  protected readonly detectorLabel: Record<string, string> = { volume: 'Volume', modelo: 'Modelo de ML' };

  constructor() {
    // o incidente pelo id: roda de novo se o id da rota mudar
    effect((onCleanup) => {
      const id = this.id();
      this.fetched.set(null);
      this.notFound.set(false);
      const sub = this.store.fetchIncident(id).subscribe({
        next: (incident) => this.fetched.set(incident),
        error: (err: HttpErrorResponse) => this.notFound.set(err.status === 404),
      });
      onCleanup(() => sub.unsubscribe());
    });

    // os alertas: de novo sempre que o incidente ganhar alerta (o novo estado chega pelo WebSocket)
    effect((onCleanup) => {
      const id = this.id();
      if (this.alertCount() === undefined) {
        return;   // incidente ainda nao carregou
      }
      const sub = this.store.fetchAlerts(id).subscribe((alerts) => this.alerts.set(alerts));
      onCleanup(() => sub.unsubscribe());
    });
  }
}
