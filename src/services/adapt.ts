import { createSeed } from '../data/seed';
import { areaCenter } from '../domain/network';
import type { AreaId, Channel, Incident, OperationsSnapshot, SupportCase } from '../types';
import type { ApiIncident, ApiMessage, ApiNotification, ApiServiceArea, ApiSubscriber, ApiSupportCase, ApiTechnician } from './api';
import { getDashboardSummary, getIncidents, getMessages, getNetworkAreas, getNetworkSites, getNotifications, getSubscribers, getSupportCases, getTechnicians } from './api';

const AREA_SLUG: Record<string, AreaId> = {
  Kilimani: 'kilimani',
  'South B': 'south-b',
  Lavington: 'lavington',
  'Kilimani West': 'kilimani-west',
  CBD: 'cbd',
};

const PLAN_ID: Record<string, string> = {
  'Home 10 Mbps': 'plan-home-10',
  'Home 20 Mbps': 'plan-home-20',
  'Business 50 Mbps': 'plan-biz-50',
  'Business 100 Mbps': 'plan-biz-100',
};

const SITE_ID: Record<string, string> = {
  'Kilimani POP': 'site-kilimani',
  'South B Tower': 'site-south-b',
  'Lavington Node': 'site-lavington',
  'CBD Core': 'site-cbd',
};

function areaId(name: string): AreaId {
  const slug = AREA_SLUG[name];
  if (!slug) throw new Error(`Unknown service area from the API: ${name}`);
  return slug;
}

function channel(source: string): Channel {
  if (source === 'SMS') return 'sms';
  if (source === 'VOICE' || source === 'PHONE') return 'voice';
  if (source === 'USSD') return 'ussd';
  return 'whatsapp';
}

function caseStatus(status: string): SupportCase['status'] {
  if (status === 'INVESTIGATING' || status === 'ESCALATED') return 'investigating';
  if (status === 'ACKNOWLEDGED') return 'assigned';
  if (status === 'RESOLVED' || status === 'CLOSED') return 'resolved';
  return 'open';
}

function priority(value: string): SupportCase['priority'] {
  if (value === 'HIGH' || value === 'CRITICAL') return 'high';
  if (value === 'LOW') return 'low';
  return 'medium';
}

function incidentStatus(status: ApiIncident['status']): Incident['status'] {
  if (status === 'ACKNOWLEDGED') return 'acknowledged';
  if (status === 'MONITORING') return 'monitoring';
  if (status === 'RESOLVED') return 'resolved';
  return 'investigating';
}

function severity(value: ApiIncident['severity']): Incident['severity'] {
  if (value === 'CRITICAL') return 'critical';
  if (value === 'MINOR') return 'info';
  return 'warning';
}

function pointNear(polygon: [number, number][], index: number): { lat: number; lng: number } {
  const [lat, lng] = polygon.length ? areaCenter(polygon) : [-1.2921, 36.8219];
  const angle = (index % 12) * (Math.PI / 6);
  const radius = 0.0035;
  return { lat: lat + Math.sin(angle) * radius, lng: lng + Math.cos(angle) * radius };
}

function mapSubscriber(item: ApiSubscriber, areaByPk: Map<number, AreaId>, offlineIncident: Map<number, string>): OperationsSnapshot['subscribers'][number] {
  return {
    id: String(item.id),
    accountId: item.account_number,
    name: item.full_name,
    phone: item.phone_number,
    area: areaByPk.get(item.service_area) ?? areaId(item.service_area_name),
    packageId: PLAN_ID[item.plan] ?? item.plan,
    status: item.status === 'SUSPENDED' ? 'suspended' : item.status === 'INACTIVE' ? 'inactive' : 'active',
    connection: item.connection_status === 'ONLINE' ? 'online' : item.connection_status === 'DEGRADED' ? 'unstable' : 'offline',
    lastSeen: item.updated_at,
    paymentStatus: 'paid',
    balance: 0,
    offlineDueToIncidentId: item.connection_status === 'OFFLINE' ? offlineIncident.get(item.service_area) : undefined,
  };
}

export async function loadApiSnapshot(): Promise<OperationsSnapshot> {
  const [summary, subscribers, cases, incidents, areas, sites, messages, notifications, technicians] = await Promise.all([
    getDashboardSummary(),
    getSubscribers(),
    getSupportCases(),
    getIncidents(),
    getNetworkAreas(),
    getNetworkSites(),
    getMessages(),
    getNotifications(),
    getTechnicians(),
  ]);
  return toSnapshot({ summary, subscribers, cases, incidents, areas, sites, messages, notifications, technicians });
}

export function toSnapshot(input: {
  summary: Awaited<ReturnType<typeof getDashboardSummary>>;
  subscribers: ApiSubscriber[];
  cases: ApiSupportCase[];
  incidents: ApiIncident[];
  areas: ApiServiceArea[];
  sites: Awaited<ReturnType<typeof getNetworkSites>>;
  messages: ApiMessage[];
  notifications: ApiNotification[];
  technicians: ApiTechnician[];
}): OperationsSnapshot {
  const catalog = createSeed();
  const areaByPk = new Map(input.areas.map((area) => [area.id, areaId(area.name)]));
  const siteByArea = new Map(input.sites.map((site) => [site.service_area, SITE_ID[site.name] ?? `site-${site.id}`]));
  const caseIncident = new Map<number, string>();
  input.incidents.forEach((incident) => {
    incident.reports.forEach((report) => {
      if (report.support_case) caseIncident.set(report.support_case, String(incident.id));
    });
  });
  const offlineIncident = new Map<number, string>();
  input.incidents
    .filter((incident) => incident.status !== 'RESOLVED')
    .forEach((incident) => offlineIncident.set(incident.service_area, String(incident.id)));

  const mappedCases: SupportCase[] = input.cases.map((item, index) => {
    const area = areaByPk.get(item.service_area) ?? areaId(item.service_area_name);
    const polygon = input.areas.find((candidate) => candidate.id === item.service_area)?.geometry ?? [];
    const point = pointNear(polygon, index);
    return {
      id: String(item.id),
      subscriberId: String(item.subscriber),
      issue: item.subject,
      channel: channel(item.source),
      area,
      priority: priority(item.priority),
      status: caseStatus(item.status),
      createdAt: item.created_at,
      lat: point.lat,
      lng: point.lng,
      incidentId: caseIncident.get(item.id),
      assigneeId: item.assigned_to || undefined,
      escalated: item.status === 'ESCALATED',
      messages: item.description
        ? [{ id: `case-msg-${item.id}`, sender: 'customer', body: item.description, at: item.created_at, channel: channel(item.source) }]
        : [],
    };
  });

  const mappedIncidents: Incident[] = input.incidents.map((item) => {
    const area = areaByPk.get(item.service_area) ?? areaId(item.service_area_name);
    const channels = new Set(input.notifications.filter((note) => note.incident === item.id).map((note) => note.channel));
    const timeline = [
      { id: `tl-${item.id}-start`, at: item.started_at, text: 'Incident opened' },
      ...(item.acknowledged_at ? [{ id: `tl-${item.id}-ack`, at: item.acknowledged_at, text: 'ISP acknowledged incident' }] : []),
      ...(item.assigned_technician_name ? [{ id: `tl-${item.id}-tech`, at: item.updated_at, text: `Technician assigned · ${item.assigned_technician_name}` }] : []),
      ...(channels.size ? [{ id: `tl-${item.id}-note`, at: item.updated_at, text: 'Notification queued for affected customers' }] : []),
      ...(item.resolved_at ? [{ id: `tl-${item.id}-done`, at: item.resolved_at, text: 'Incident resolved' }] : []),
    ];
    return {
      id: String(item.id),
      code: item.incident_number,
      title: item.title,
      area,
      siteId: siteByArea.get(item.service_area) ?? `site-${item.service_area}`,
      status: item.assigned_technician && item.status === 'ACKNOWLEDGED' ? 'assigned' : incidentStatus(item.status),
      severity: severity(item.severity),
      affectedSubscribers: item.affected_subscribers,
      reportCount: item.report_count,
      startedAt: item.started_at,
      resolvedAt: item.resolved_at ?? undefined,
      technicianId: item.assigned_technician ? String(item.assigned_technician) : undefined,
      notified: channels.size
        ? {
            channel: channels.has('WHATSAPP') && channels.has('SMS') ? 'both' : channels.has('SMS') ? 'sms' : 'whatsapp',
            at: item.updated_at,
          }
        : undefined,
      timeline,
    };
  });

  const openByArea = new Map<AreaId, number>();
  mappedCases.forEach((item) => {
    if (item.status !== 'resolved') openByArea.set(item.area, (openByArea.get(item.area) ?? 0) + 1);
  });

  return {
    subscribers: input.subscribers.map((item) => mapSubscriber(item, areaByPk, offlineIncident)),
    cases: mappedCases,
    incidents: mappedIncidents,
    sites: input.sites.map((site) => {
      const area = areaByPk.get(site.service_area) ?? areaId(site.service_area_name);
      const open = openByArea.get(area) ?? 0;
      return {
        id: SITE_ID[site.name] ?? `site-${site.id}`,
        name: site.name,
        areaIds: [area],
        lat: Number(site.latitude),
        lng: Number(site.longitude),
        served: input.areas.find((item) => item.id === site.service_area)?.subscriber_count ?? 0,
        openIssueBaseline: open,
        openIssueSnapshot: open,
      };
    }),
    areas: input.areas.map((area) => ({
      id: areaId(area.name),
      name: area.name,
      polygon: Array.isArray(area.geometry) ? area.geometry : [],
      remoteId: area.id,
    })),
    reports: mappedCases
      .filter((item) => item.status !== 'resolved')
      .map((item) => ({
        id: `rpt-${item.id}`,
        area: item.area,
        issue: item.issue,
        channel: item.channel,
        lat: item.lat,
        lng: item.lng,
        at: item.createdAt,
        caseId: item.id,
        incidentId: item.incidentId,
      })),
    messages: input.messages.map((item) => ({
      id: String(item.id),
      subscriberId: item.subscriber ? String(item.subscriber) : undefined,
      recipientLabel: input.subscribers.find((person) => person.id === item.subscriber)?.full_name ?? 'Subscriber',
      channel: channel(item.channel),
      body: item.body,
      direction: item.direction === 'INBOUND' ? 'inbound' as const : 'outbound' as const,
      status: item.status === 'DELIVERED' ? 'delivered' as const : item.status === 'FAILED' ? 'failed' as const : item.status === 'PENDING' ? 'pending' as const : 'sent' as const,
      at: item.created_at,
    })),
    plans: catalog.plans,
    payments: catalog.payments,
    notifications: input.notifications.map((item) => ({
      id: String(item.id),
      title: item.title,
      description: item.body,
      at: item.created_at,
      read: false,
      link: item.incident ? { kind: 'incident' as const, id: String(item.incident) } : { kind: 'route' as const, to: '/dashboard/messages' },
      category: item.title.toLowerCase().includes('restor') ? 'outage' as const : 'support' as const,
    })),
    technicians: input.technicians.map((item) => ({
      id: String(item.id),
      name: item.name,
      phone: item.phone_number,
      email: item.email,
      status: item.status,
      serviceAreaId: String(item.service_area),
      serviceAreaName: item.service_area_name,
    })),
    activities: input.summary.recent_activity.map((item) => ({ id: String(item.id), at: item.created_at, text: item.text })),
    team: catalog.team,
    settings: catalog.settings,
    census: { active: input.summary.active_subscribers, online: input.summary.online_subscribers },
    hiddenOpenIssues: 0,
    hiddenAttention: 0,
    nextIncidentNumber: 110,
    openIssues: input.summary.open_issues,
    activeOutages: input.summary.active_outages,
  };
}
