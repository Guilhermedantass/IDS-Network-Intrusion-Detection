import { Routes } from '@angular/router';
import { IncidentList } from './incidents/incident-list';

export const routes: Routes = [
  { path: '', component: IncidentList, title: 'IDS · Incidentes' },
];
