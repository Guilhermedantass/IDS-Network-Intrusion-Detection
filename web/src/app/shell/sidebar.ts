import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { IncidentStore } from '../incidents/incident-store';

/** Barra lateral: navegacao e, no rodape, o estado da conexao com a API (vale para o sistema todo). */
@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.scss',
})
export class Sidebar {
  protected readonly store = inject(IncidentStore);

  protected readonly statusLabel = {
    conectando: 'Conectando à API',
    conectado: 'Conectado à API',
    desconectado: 'API fora do ar',
  } as const;
}
