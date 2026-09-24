import type { AreaHealth, AreaId, FieldReport, Incident, NetworkSite, SupportCase } from '../types';

export const AREA_SITE: Record<AreaId, string> = {
  kilimani: 'site-kilimani',
  'kilimani-west': 'site-kilimani',
  'south-b': 'site-south-b',
  lavington: 'site-lavington',
  cbd: 'site-cbd',
};

/** Share of a site's served customers that sit in each area. */
export const AREA_SHARE: Record<AreaId, number> = {
  kilimani: 0.62,
  'kilimani-west': 0.38,
  'south-b': 1,
  lavington: 1,
  cbd: 1,
};

export function areaHealth(areaId: AreaId, incidents: Incident[]): AreaHealth {
  const active = incidents.filter((incident) => incident.area === areaId && incident.status !== 'resolved');
  if (active.some((incident) => incident.severity === 'critical')) return 'outage';
  if (active.length > 0) return 'degraded';
  return 'operational';
}

export function siteHealth(site: NetworkSite, incidents: Incident[]): AreaHealth {
  const ranks = site.areaIds.map((areaId) => areaHealth(areaId, incidents));
  if (ranks.includes('outage')) return 'outage';
  if (ranks.includes('degraded')) return 'degraded';
  return 'operational';
}

export function siteOpenIssues(site: NetworkSite, cases: SupportCase[]) {
  const live = cases.filter((item) => site.areaIds.includes(item.area) && item.status !== 'resolved').length;
  return Math.max(0, site.openIssueBaseline + (live - site.openIssueSnapshot));
}

export function openIssueCount(cases: SupportCase[], hidden: number) {
  return hidden + cases.filter((item) => item.status !== 'resolved').length;
}

export function attentionCount(cases: SupportCase[], hidden: number) {
  return hidden + cases.filter((item) => item.status !== 'resolved' && item.priority === 'high').length;
}

export function activeIncidents(incidents: Incident[]) {
  return incidents
    .filter((incident) => incident.status !== 'resolved')
    .sort((a, b) => {
      const severity = Number(b.severity === 'critical') - Number(a.severity === 'critical');
      if (severity !== 0) return severity;
      return new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime();
    });
}

export function primaryIncident(incidents: Incident[]) {
  return activeIncidents(incidents)[0];
}

export function incidentForArea(areaId: AreaId, incidents: Incident[]) {
  return activeIncidents(incidents).find((incident) => incident.area === areaId);
}

export function visibleReports(reports: FieldReport[], cases: SupportCase[], incidents: Incident[]) {
  return reports.filter((report) => {
    if (report.caseId) {
      const supportCase = cases.find((item) => item.id === report.caseId);
      return Boolean(supportCase && supportCase.status !== 'resolved');
    }
    return incidents.some((incident) => incident.area === report.area && incident.status !== 'resolved');
  });
}

export function areaCenter(polygon: [number, number][]): [number, number] {
  const lat = polygon.reduce((sum, point) => sum + point[0], 0) / polygon.length;
  const lng = polygon.reduce((sum, point) => sum + point[1], 0) / polygon.length;
  return [lat, lng];
}

export function healthLabel(health: AreaHealth, incident?: Incident) {
  if (health === 'operational' || !incident) return 'Operational';
  const workflow = incident.status.charAt(0).toUpperCase() + incident.status.slice(1);
  if (health === 'outage') return `Outage · ${workflow}`;
  return `Degraded · ${workflow}`;
}
