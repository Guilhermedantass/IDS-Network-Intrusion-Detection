import { DatePipe, DecimalPipe, PercentPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, input, numberAttribute, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Observable, catchError, of, switchMap, timer } from 'rxjs';

import { Clock } from '../clock';
import { BlockState, blockState } from '../sensors/block-rules';
import { Sensor } from '../sensors/sensor';
import { SensorApi } from '../sensors/sensor-api';
import { Incident } from './incident';
import { IncidentAlert } from './incident-alert';
import { formatDuration, isActive } from './incident-rules';
import { IncidentStore } from './incident-store';

/**
 * Um incidente e os alertas dele (rota 'incidents/:id').
 *
 * O incidente vem do store quando esta na lista (e ai se atualiza ao vivo pelo WebSocket);
 * se for antigo, busca pelo id. Os alertas sao buscados de novo sempre que o incidente ganha um alerta.
 *
 * Resposta (IPS): cada origem dos alertas pode ser bloqueada no firewall do sensor que detectou. O pedido vai
 * para a API e o sensor aplica no proximo heartbeat; por isso o sensor e buscado de novo a cada 3 s.
 */
@Component({
  selector: 'app-incident-detail',
  imports: [DatePipe, DecimalPipe, PercentPipe, RouterLink],
  templateUrl: './incident-detail.html',
  styleUrl: './incident-detail.scss',
})
export class IncidentDetail {
  private readonly store = inject(IncidentStore);
  private readonly sensorApi = inject(SensorApi);
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

  /** O sensor do incidente: undefined = carregando; null = a API nao conhece (servico desligado). */
  protected readonly sensor = signal<Sensor | null | undefined>(undefined);
  protected readonly sending = signal<string | null>(null);     // IP com pedido a caminho
  protected readonly blockFailed = signal<string | null>(null);

  private readonly sensorName = computed(() => this.incident()?.sensor);

  /** As origens dos alertas, a que mais apareceu primeiro. Alerta sem srcIp (DDoS) nao entra. */
  protected readonly sources = computed(() => {
    const counts = new Map<string, number>();
    for (const a of this.alerts() ?? []) {
      if (a.srcIp) {
        counts.set(a.srcIp, (counts.get(a.srcIp) ?? 0) + 1);
      }
    }
    return [...counts].map(([ip, count]) => ({ ip, count })).sort((a, b) => b.count - a.count);
  });
  protected readonly manySources = computed(() => this.alerts()?.some((a) => a.srcIp === null) ?? false);

  protected readonly blockLabel: Record<BlockState, string> = {
    none: '',
    blocking: 'Bloqueando…',
    blocked: 'Bloqueado',
    unblocking: 'Desbloqueando…',
    protected: 'Protegido: é este PC, o gateway ou a API',
  };

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

    // o sensor do incidente, a cada 3 s (para ver o bloqueio sair de "Bloqueando…" para "Bloqueado")
    effect((onCleanup) => {
      const name = this.sensorName();
      if (name === undefined) {
        return;
      }
      const sub = timer(0, 3000)
        .pipe(
          switchMap(() => this.sensorApi.list().pipe(catchError(() => of(null)))),
        )
        .subscribe((list) => {
          if (list) {
            this.sensor.set(list.find((s) => s.name === name) ?? null);
          }
        });
      onCleanup(() => sub.unsubscribe());
    });
  }

  protected blockState(s: Sensor, ip: string): BlockState {
    return blockState(s, ip);
  }

  /** Bloqueia, ou desbloqueia se ja estiver bloqueado (ou a caminho). */
  protected toggleBlock(s: Sensor, ip: string): void {
    const state = blockState(s, ip);
    const request: Observable<Sensor> =
      state === 'blocked' || state === 'blocking' ? this.sensorApi.unblock(s.name, ip) : this.sensorApi.block(s.name, ip);
    this.sending.set(ip);
    this.blockFailed.set(null);
    request.subscribe({
      next: (updated) => {
        this.sensor.set(updated);
        this.sending.set(null);
      },
      error: (err: HttpErrorResponse) => {
        this.sending.set(null);
        this.blockFailed.set(
          err.status === 400 ? `A API recusou bloquear ${ip}: é um IP protegido ou inválido.`
          : err.status === 404 ? `O sensor ${s.name} não está mais conectado à API.`
          : 'Não foi possível falar com a API.',
        );
      },
    });
  }
}
