import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from '../config';
import { CaptureRequest, Sensor } from './sensor';

/** As chamadas de /api/sensors. Todas devolvem o sensor ja com o pedido novo em `desired`. */
@Injectable({ providedIn: 'root' })
export class SensorApi {
  private readonly http = inject(HttpClient);

  list(): Observable<Sensor[]> {
    return this.http.get<Sensor[]>(`${API_URL}/api/sensors`);
  }

  capture(name: string, request: CaptureRequest): Observable<Sensor> {
    return this.http.put<Sensor>(`${this.url(name)}/capture`, request);
  }

  block(name: string, ip: string): Observable<Sensor> {
    return this.http.put<Sensor>(`${this.url(name)}/blocked/${encodeURIComponent(ip)}`, null);
  }

  unblock(name: string, ip: string): Observable<Sensor> {
    return this.http.delete<Sensor>(`${this.url(name)}/blocked/${encodeURIComponent(ip)}`);
  }

  private url(name: string): string {
    return `${API_URL}/api/sensors/${encodeURIComponent(name)}`;
  }
}
