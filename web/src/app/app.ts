import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { Sidebar } from './shell/sidebar';

@Component({
  imports: [RouterOutlet, Sidebar],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {}
