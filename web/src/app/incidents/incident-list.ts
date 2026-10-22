import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';

import { isActive } from './incident-rules';
import { IncidentStore } from './incident-store';

/**
 * A tela de incidentes ao vivo (rota ''). Conecta no store ao abrir e desconecta ao sair.
 * O relogio (now) atualiza a cada 1 s para o status ativo/encerrado mudar sozinho: um incidente
 * encerra justamente quando NAO chega nada, entao sem relogio a tela nunca saberia.
 */
@Component({
  selector: 'app-incident-list',
  imports: [DatePipe, DecimalPipe],
  templateUrl: './incident-list.html',
  styleUrl: './incident-list.scss',
})
export class IncidentList implements OnInit, OnDestroy {
  protected readonly store = inject(IncidentStore);
  protected readonly now = signal(Date.now());
  protected readonly isActive = isActive;   // para usar no template

  /** Quantos ataques estao acontecendo agora; recalcula quando a lista ou o relogio mudam. */
  protected readonly activeCount = computed(
    () => this.store.incidents().filter((i) => isActive(i, this.now())).length,
  );

  private clock?: ReturnType<typeof setInterval>;

  ngOnInit(): void {
    this.store.connect();
    this.clock = setInterval(() => this.now.set(Date.now()), 1000);
  }

  ngOnDestroy(): void {
    clearInterval(this.clock);
    this.store.disconnect();
  }
}
