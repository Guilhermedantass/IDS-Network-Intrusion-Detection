import { Injectable, signal } from '@angular/core';

/**
 * Um relogio para o app todo: now() muda a cada 1 s. Usado para o status ativo/encerrado mudar sozinho
 * (um incidente encerra justamente quando NAO chega nada, entao so o relogio percebe).
 * Um so para todas as telas, em vez de um setInterval por componente.
 */
@Injectable({ providedIn: 'root' })
export class Clock {
  private readonly _now = signal(Date.now());
  readonly now = this._now.asReadonly();

  constructor() {
    setInterval(() => this._now.set(Date.now()), 1000);
  }
}
