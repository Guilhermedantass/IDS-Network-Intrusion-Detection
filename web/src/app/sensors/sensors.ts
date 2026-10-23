import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Observable, catchError, switchMap, timer } from 'rxjs';

import { Clock } from '../clock';
import { formatDuration } from '../incidents/incident-rules';
import { BlockState, blockState, blockedIps } from './block-rules';
import { CaptureRequest, Sensor } from './sensor';
import { SensorApi } from './sensor-api';

const POLL_MS = 3000;

/**
 * Controle dos sensores (rota 'sensors'): ver se cada sensor esta online, iniciar/parar a captura e
 * ver/desbloquear os IPs bloqueados (o bloqueio e feito na tela do incidente).
 *
 * O dashboard nao fala com o sensor: ele muda o pedido na API, e o sensor aplica no proximo heartbeat
 * (ate 5 s). Por isso a tela mostra "Iniciando..." enquanto o pedido e o estado sao diferentes.
 * A lista e buscada de novo a cada 3 s.
 */
@Component({
  selector: 'app-sensors',
  imports: [DatePipe, DecimalPipe],
  templateUrl: './sensors.html',
  styleUrl: './sensors.scss',
})
export class Sensors {
  private readonly api = inject(SensorApi);
  protected readonly now = inject(Clock).now;

  protected readonly sensors = signal<Sensor[] | null>(null);   // null = carregando
  protected readonly failed = signal(false);
  protected readonly sending = signal<string | null>(null);     // sensor com pedido a caminho

  /** Interface escolhida no select de cada sensor (enquanto nao escolhe, vale a atual). */
  protected readonly chosen = signal<Record<string, string>>({});

  constructor() {
    // timer(0, 3000): agora e a cada 3 s; switchMap cancela a busca anterior se ela atrasar;
    // takeUntilDestroyed para tudo quando a pagina sai
    timer(0, POLL_MS)
      .pipe(
        switchMap(() =>
          this.api.list().pipe(
            catchError(() => {
              this.failed.set(true);
              return EMPTY;
            }),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((list) => {
        this.sensors.set(list);
        this.failed.set(false);
      });
  }

  protected interfaceOf(s: Sensor): string {
    return this.chosen()[s.name] ?? s.desired.interface ?? s.reported.interface ?? '';
  }

  protected choose(s: Sensor, iface: string): void {
    this.chosen.update((c) => ({ ...c, [s.name]: iface }));
  }

  /** O que a tela diz sobre o sensor: o pedido ainda nao aplicado vem antes do estado. */
  protected state(s: Sensor): { text: string; kind: 'off' | 'pending' | 'on' | 'idle' } {
    const r = s.reported;
    const d = s.desired;
    if (!s.online) {
      return { text: 'Offline', kind: 'off' };
    }
    if (d.capture && (!r.capturing || (d.interface !== null && d.interface !== r.interface))) {
      return r.error ? { text: 'Parado com erro', kind: 'idle' } : { text: `Iniciando em ${d.interface ?? 'interface padrão'}…`, kind: 'pending' };
    }
    if (!d.capture && r.capturing) {
      return { text: 'Parando…', kind: 'pending' };
    }
    if (r.capturing && r.startedAt) {
      return { text: `Capturando em ${r.interface} há ${formatDuration(this.now() - Date.parse(r.startedAt))}`, kind: 'on' };
    }
    return { text: 'Parado', kind: 'idle' };
  }

  protected toggle(s: Sensor): void {
    const iface = this.interfaceOf(s) || null;
    const request: CaptureRequest = { capture: !s.desired.capture, interface: iface };
    this.send(s, this.api.capture(s.name, request));
  }

  protected readonly blockedIps = blockedIps;

  protected blockState(s: Sensor, ip: string): BlockState {
    return blockState(s, ip);
  }

  protected unblock(s: Sensor, ip: string): void {
    this.send(s, this.api.unblock(s.name, ip));
  }

  private send(s: Sensor, request: Observable<Sensor>): void {
    this.sending.set(s.name);
    request.subscribe({
      next: (updated) => {
        this.sensors.update((list) => list?.map((x) => (x.name === updated.name ? updated : x)) ?? null);
        this.sending.set(null);
      },
      error: () => this.sending.set(null),
    });
  }
}
