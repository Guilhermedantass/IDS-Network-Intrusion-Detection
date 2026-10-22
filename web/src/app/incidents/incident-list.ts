import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Clock } from '../clock';
import { isActive } from './incident-rules';
import { IncidentStore } from './incident-store';

/** A tela de incidentes ao vivo (rota ''). A conexao com a API fica no App; aqui so le o store. */
@Component({
  selector: 'app-incident-list',
  imports: [DatePipe, DecimalPipe, RouterLink],
  templateUrl: './incident-list.html',
  styleUrl: './incident-list.scss',
})
export class IncidentList {
  protected readonly store = inject(IncidentStore);
  protected readonly now = inject(Clock).now;
  protected readonly isActive = isActive;   // para usar no template

  /** Quantos ataques estao acontecendo agora; recalcula quando a lista ou o relogio mudam. */
  protected readonly activeCount = computed(
    () => this.store.incidents().filter((i) => isActive(i, this.now())).length,
  );
}
