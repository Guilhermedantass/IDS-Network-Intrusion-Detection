import { Routes } from '@angular/router';
import { IncidentDetail } from './incidents/incident-detail';
import { IncidentList } from './incidents/incident-list';
import { Overview } from './overview/overview';
import { Sensors } from './sensors/sensors';

export const routes: Routes = [
  { path: '', redirectTo: 'overview', pathMatch: 'full' },
  { path: 'overview', component: Overview, title: 'IDS · Visão geral' },
  { path: 'incidents', component: IncidentList, title: 'IDS · Incidentes' },
  { path: 'incidents/:id', component: IncidentDetail, title: 'IDS · Incidente' },
  { path: 'sensors', component: Sensors, title: 'IDS · Sensores' },
];
