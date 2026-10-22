import { Routes } from '@angular/router';
import { IncidentDetail } from './incidents/incident-detail';
import { IncidentList } from './incidents/incident-list';

export const routes: Routes = [
  { path: '', redirectTo: 'incidents', pathMatch: 'full' },
  { path: 'incidents', component: IncidentList, title: 'IDS · Incidentes' },
  { path: 'incidents/:id', component: IncidentDetail, title: 'IDS · Incidente' },
];
