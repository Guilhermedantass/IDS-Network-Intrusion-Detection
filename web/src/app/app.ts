import { Component, OnInit, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { IncidentStore } from './incidents/incident-store';
import { Sidebar } from './shell/sidebar';

@Component({
  imports: [RouterOutlet, Sidebar],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App implements OnInit {
  private readonly store = inject(IncidentStore);

  ngOnInit(): void {
    // o WebSocket fica ligado o tempo todo, em qualquer pagina (o status na barra lateral vale sempre)
    this.store.connect();
  }
}
