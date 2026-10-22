import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Client } from '@stomp/stompjs';
import { Observable } from 'rxjs';

import { API_URL, WS_URL } from '../config';
import { Incident } from './incident';
import { IncidentAlert } from './incident-alert';
import { upsertIncident } from './incident-rules';

export type ConnectionStatus = 'conectando' | 'conectado' | 'desconectado';

/**
 * Guarda a lista de incidentes e mantem ela atualizada: GET /api/incidents para a lista inicial,
 * WebSocket (/topic/incidents) para o que muda depois. Os componentes so leem os signals daqui.
 */
@Injectable({ providedIn: 'root' })
export class IncidentStore {
  private readonly http = inject(HttpClient);

  private readonly _incidents = signal<Incident[]>([]);
  private readonly _status = signal<ConnectionStatus>('conectando');

  // so leitura para os componentes: quem muda a lista e o store
  readonly incidents = this._incidents.asReadonly();
  readonly status = this._status.asReadonly();

  private client?: Client;

  load(): void {
    this.http.get<Incident[]>(`${API_URL}/api/incidents`).subscribe({
      next: (list) => this._incidents.set(list),   // ja vem ordenada (mais recente primeiro)
      error: (err) => console.error('Falha ao buscar incidentes', err),
    });
  }

  connect(): void {
    if (this.client) {
      return;   // ja conectado (ou tentando)
    }
    this._status.set('conectando');

    const client = new Client({ brokerURL: WS_URL, reconnectDelay: 5000 });   // se cair, tenta de novo a cada 5 s

    client.onConnect = () => {
      this._status.set('conectado');
      client.subscribe('/topic/incidents', (msg) => {
        const incident = JSON.parse(msg.body) as Incident;
        this._incidents.update((list) => upsertIncident(list, incident));
      });
      // a cada conexao (a primeira e as reconexoes): o que mudou enquanto estava fora nao chega pelo WebSocket
      this.load();
    };
    client.onWebSocketClose = () => this._status.set('desconectado');

    client.activate();
    this.client = client;
  }

  disconnect(): void {
    this.client?.deactivate();
    this.client = undefined;
  }

  /** Um incidente pelo id: pode ser antigo, fora dos 50 que a lista carrega. Erro 404 se nao existe. */
  fetchIncident(id: number): Observable<Incident> {
    return this.http.get<Incident>(`${API_URL}/api/incidents/${id}`);
  }

  /** Os alertas de um incidente, em ordem de tempo. */
  fetchAlerts(incidentId: number): Observable<IncidentAlert[]> {
    return this.http.get<IncidentAlert[]>(`${API_URL}/api/alerts`, { params: { incident: incidentId } });
  }
}
