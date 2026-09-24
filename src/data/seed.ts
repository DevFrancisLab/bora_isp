import { areaCenter } from '../domain/network';
import { atNairobi, minutesAgo } from '../domain/format';
import type {
  Activity,
  AppNotification,
  CommMessage,
  ConversationMessage,
  FieldReport,
  Incident,
  NetworkSite,
  OperationsSnapshot,
  Payment,
  Plan,
  SettingsState,
  Subscriber,
  SupportCase,
  TeamMember,
  Technician,
} from '../types';
import { SERVICE_AREAS } from './geo';

const rel = minutesAgo;

function msg(id: string, sender: ConversationMessage['sender'], body: string, at: string, channel?: ConversationMessage['channel']): ConversationMessage {
  return { id, sender, body, at, channel };
}

const plans: Plan[] = [
  { id: 'plan-home-10', name: 'Home 10 Mbps', speedMbps: 10, priceKes: 1500, segment: 'Home', active: true },
  { id: 'plan-home-20', name: 'Home 20 Mbps', speedMbps: 20, priceKes: 2000, segment: 'Home', active: true },
  { id: 'plan-biz-50', name: 'Business 50 Mbps', speedMbps: 50, priceKes: 5000, segment: 'Business', active: true },
  { id: 'plan-biz-100', name: 'Business 100 Mbps', speedMbps: 100, priceKes: 8000, segment: 'Business', active: true },
];

const subscribers: Subscriber[] = [
  { id: 'sub-mary', accountId: 'SUB-00124', name: 'Mary Wanjiku', phone: '+254712438221', area: 'kilimani', packageId: 'plan-home-20', status: 'active', connection: 'offline', lastSeen: rel(48), paymentStatus: 'paid', balance: 0, offlineDueToIncidentId: 'inc-104' },
  { id: 'sub-james', accountId: 'SUB-00188', name: 'James Ochieng', phone: '+254722615904', area: 'kilimani', packageId: 'plan-home-10', status: 'active', connection: 'offline', lastSeen: rel(40), paymentStatus: 'paid', balance: 0, offlineDueToIncidentId: 'inc-104' },
  { id: 'sub-grace', accountId: 'SUB-00211', name: 'Grace Njeri', phone: '+254733890112', area: 'kilimani', packageId: 'plan-home-20', status: 'active', connection: 'unstable', lastSeen: rel(12), paymentStatus: 'pending', balance: 2000 },
  { id: 'sub-peter', accountId: 'SUB-00156', name: 'Peter Njoroge', phone: '+254711203884', area: 'kilimani', packageId: 'plan-biz-50', status: 'active', connection: 'online', lastSeen: rel(1), paymentStatus: 'paid', balance: 0 },
  { id: 'sub-aisha', accountId: 'SUB-00302', name: 'Aisha Mohammed', phone: '+254701554873', area: 'kilimani-west', packageId: 'plan-home-10', status: 'active', connection: 'online', lastSeen: rel(4), paymentStatus: 'paid', balance: 0 },
  { id: 'sub-hassan', accountId: 'SUB-00276', name: 'Hassan Abdi', phone: '+254745221098', area: 'kilimani-west', packageId: 'plan-home-20', status: 'active', connection: 'online', lastSeen: rel(20), paymentStatus: 'paid', balance: 0 },
  { id: 'sub-david', accountId: 'SUB-00415', name: 'David Kipchoge', phone: '+254720667331', area: 'south-b', packageId: 'plan-home-10', status: 'active', connection: 'offline', lastSeen: rel(90), paymentStatus: 'overdue', balance: 1500, offlineDueToIncidentId: 'inc-102' },
  { id: 'sub-fatuma', accountId: 'SUB-00440', name: 'Fatuma Ali', phone: '+254711908221', area: 'south-b', packageId: 'plan-home-20', status: 'active', connection: 'unstable', lastSeen: rel(25), paymentStatus: 'pending', balance: 2000 },
  { id: 'sub-mercy', accountId: 'SUB-00488', name: 'Mercy Chebet', phone: '+254708334512', area: 'south-b', packageId: 'plan-home-10', status: 'active', connection: 'online', lastSeen: rel(8), paymentStatus: 'paid', balance: 0 },
  { id: 'sub-samuel', accountId: 'SUB-00512', name: 'Samuel Kariuki', phone: '+254722100483', area: 'lavington', packageId: 'plan-biz-50', status: 'active', connection: 'online', lastSeen: rel(3), paymentStatus: 'paid', balance: 0 },
  { id: 'sub-ann', accountId: 'SUB-00540', name: 'Ann Wairimu', phone: '+254733221760', area: 'lavington', packageId: 'plan-home-20', status: 'active', connection: 'online', lastSeen: rel(6), paymentStatus: 'paid', balance: 0 },
  { id: 'sub-daniel', accountId: 'SUB-00571', name: 'Daniel Kiptoo', phone: '+254701882345', area: 'lavington', packageId: 'plan-biz-100', status: 'active', connection: 'online', lastSeen: rel(2), paymentStatus: 'paid', balance: 0 },
  { id: 'sub-catherine', accountId: 'SUB-00590', name: 'Catherine Wambui', phone: '+254715440218', area: 'lavington', packageId: 'plan-home-10', status: 'active', connection: 'online', lastSeen: rel(9), paymentStatus: 'paid', balance: 0 },
  { id: 'sub-lucy', accountId: 'SUB-00603', name: 'Lucy Akinyi', phone: '+254715662190', area: 'cbd', packageId: 'plan-biz-50', status: 'active', connection: 'unstable', lastSeen: rel(15), paymentStatus: 'paid', balance: 0 },
  { id: 'sub-joseph', accountId: 'SUB-00620', name: 'Joseph Mutua', phone: '+254724908331', area: 'cbd', packageId: 'plan-home-10', status: 'suspended', connection: 'offline', lastSeen: rel(60 * 26), paymentStatus: 'overdue', balance: 2000 },
  { id: 'sub-esther', accountId: 'SUB-00655', name: 'Esther Nyambura', phone: '+254700214587', area: 'cbd', packageId: 'plan-home-20', status: 'active', connection: 'online', lastSeen: rel(5), paymentStatus: 'paid', balance: 0 },
  { id: 'sub-michael', accountId: 'SUB-00680', name: 'Michael Odhiambo', phone: '+254798331204', area: 'cbd', packageId: 'plan-biz-100', status: 'pending', connection: 'offline', lastSeen: rel(60 * 5), paymentStatus: 'pending', balance: 8000 },
];

const cases: SupportCase[] = [
  {
    id: 'case-mary',
    subscriberId: 'sub-mary',
    issue: 'Internet Down',
    channel: 'whatsapp',
    area: 'kilimani',
    priority: 'high',
    status: 'open',
    createdAt: rel(2),
    lat: -1.2948,
    lng: 36.7905,
    incidentId: 'inc-104',
    messages: [
      msg('m1', 'customer', 'My internet has been down since morning.', rel(2), 'whatsapp'),
      msg('m2', 'agent', "I found your account. I'm checking for any network issues in your area.", rel(1), 'whatsapp'),
      msg('m3', 'system', '11 similar reports detected within Kilimani.', rel(1)),
      msg('m4', 'agent', 'There is currently an active service issue affecting your area. Our team is investigating.', rel(1), 'whatsapp'),
    ],
  },
  {
    id: 'case-james',
    subscriberId: 'sub-james',
    issue: 'Internet Down',
    channel: 'voice',
    area: 'kilimani',
    priority: 'high',
    status: 'investigating',
    createdAt: rel(16),
    lat: -1.2888,
    lng: 36.7822,
    incidentId: 'inc-104',
    messages: [
      msg('j1', 'customer', 'Called to report no connection since 8am. Router lights are red.', rel(16), 'voice'),
      msg('j2', 'system', 'Case linked to INC-104 Kilimani Service Disruption.', rel(15)),
    ],
  },
  {
    id: 'case-grace',
    subscriberId: 'sub-grace',
    issue: 'Connection Unstable',
    channel: 'whatsapp',
    area: 'kilimani',
    priority: 'medium',
    status: 'open',
    createdAt: rel(28),
    lat: -1.2972,
    lng: 36.7936,
    incidentId: 'inc-104',
    messages: [msg('g1', 'customer', 'It connects then drops every few minutes.', rel(28), 'whatsapp')],
  },
  {
    id: 'case-david',
    subscriberId: 'sub-david',
    issue: 'Slow Internet',
    channel: 'sms',
    area: 'south-b',
    priority: 'medium',
    status: 'investigating',
    createdAt: rel(41),
    lat: -1.3095,
    lng: 36.8288,
    incidentId: 'inc-102',
    messages: [msg('d1', 'customer', 'Speeds are very low this morning.', rel(41), 'sms')],
  },
  {
    id: 'case-fatuma',
    subscriberId: 'sub-fatuma',
    issue: 'Internet Down',
    channel: 'ussd',
    area: 'south-b',
    priority: 'high',
    status: 'open',
    createdAt: rel(54),
    lat: -1.3168,
    lng: 36.8385,
    incidentId: 'inc-102',
    messages: [msg('f1', 'customer', 'USSD session: customer confirmed total loss of service.', rel(54), 'ussd')],
  },
  {
    id: 'case-mercy',
    subscriberId: 'sub-mercy',
    issue: 'Slow Internet',
    channel: 'whatsapp',
    area: 'south-b',
    priority: 'medium',
    status: 'open',
    createdAt: rel(70),
    lat: -1.3122,
    lng: 36.8264,
    incidentId: 'inc-102',
    messages: [msg('me1', 'customer', 'Pages load, but video keeps buffering.', rel(70), 'whatsapp')],
  },
  {
    id: 'case-samuel',
    subscriberId: 'sub-samuel',
    issue: 'Slow Internet',
    channel: 'whatsapp',
    area: 'lavington',
    priority: 'low',
    status: 'open',
    createdAt: rel(95),
    lat: -1.2768,
    lng: 36.7662,
    messages: [msg('s1', 'customer', 'Office link is slower than usual. No total outage.', rel(95), 'whatsapp')],
  },
  {
    id: 'case-lucy',
    subscriberId: 'sub-lucy',
    issue: 'Connection Unstable',
    channel: 'voice',
    area: 'cbd',
    priority: 'medium',
    status: 'assigned',
    createdAt: rel(180),
    lat: -1.2822,
    lng: 36.8268,
    assigneeId: 'team-nelly',
    messages: [
      msg('l1', 'customer', 'Shop connection drops during card payments.', rel(180), 'voice'),
      msg('l2', 'system', 'Assigned to Nelly Chebet.', rel(150)),
    ],
  },
  {
    id: 'case-joseph',
    subscriberId: 'sub-joseph',
    issue: 'Connection Unstable',
    channel: 'sms',
    area: 'cbd',
    priority: 'low',
    status: 'open',
    createdAt: rel(300),
    lat: -1.2884,
    lng: 36.8195,
    messages: [msg('jo1', 'customer', 'Service was unstable before the account was suspended.', rel(300), 'sms')],
  },
  {
    id: 'case-hassan',
    subscriberId: 'sub-hassan',
    issue: 'Internet Down',
    channel: 'whatsapp',
    area: 'kilimani-west',
    priority: 'low',
    status: 'resolved',
    createdAt: rel(60 * 20),
    lat: -1.2965,
    lng: 36.7624,
    messages: [
      msg('h1', 'customer', 'No internet last night.', rel(60 * 20), 'whatsapp'),
      msg('h2', 'agent', 'Service was restored. Please confirm you are back online.', rel(60 * 18), 'whatsapp'),
    ],
  },
];

const incidents: Incident[] = [
  {
    id: 'inc-104',
    code: 'INC-104',
    title: 'Kilimani Service Disruption',
    area: 'kilimani',
    siteId: 'site-kilimani',
    status: 'investigating',
    severity: 'critical',
    affectedSubscribers: 24,
    reportCount: 11,
    startedAt: atNairobi(8, 42),
    timeline: [
      { id: 't1', at: atNairobi(8, 42), text: 'First customer report received' },
      { id: 't2', at: atNairobi(8, 45), text: 'Multiple nearby reports detected' },
      { id: 't3', at: atNairobi(8, 47), text: 'Incident created' },
    ],
  },
  {
    id: 'inc-102',
    code: 'INC-102',
    title: 'South B Connectivity Issue',
    area: 'south-b',
    siteId: 'site-south-b',
    status: 'monitoring',
    severity: 'warning',
    affectedSubscribers: 13,
    reportCount: 6,
    startedAt: atNairobi(7, 28),
    timeline: [
      { id: 's1', at: atNairobi(7, 15), text: 'First customer report received' },
      { id: 's2', at: atNairobi(7, 28), text: 'Incident created' },
      { id: 's3', at: atNairobi(7, 40), text: 'Incident placed under monitoring' },
    ],
  },
];

const sites: NetworkSite[] = [
  { id: 'site-kilimani', name: 'Kilimani POP', areaIds: ['kilimani', 'kilimani-west'], lat: -1.2916, lng: 36.7868, served: 428, openIssueBaseline: 7, openIssueSnapshot: 0 },
  { id: 'site-south-b', name: 'South B Tower', areaIds: ['south-b'], lat: -1.3132, lng: 36.8338, served: 266, openIssueBaseline: 6, openIssueSnapshot: 0 },
  { id: 'site-lavington', name: 'Lavington Node', areaIds: ['lavington'], lat: -1.2794, lng: 36.7698, served: 312, openIssueBaseline: 4, openIssueSnapshot: 0 },
  { id: 'site-cbd', name: 'CBD Core', areaIds: ['cbd'], lat: -1.2846, lng: 36.8234, served: 278, openIssueBaseline: 5, openIssueSnapshot: 0 },
];

sites.forEach((site) => {
  site.openIssueSnapshot = cases.filter((item) => site.areaIds.includes(item.area) && item.status !== 'resolved').length;
});

function jitter(lat: number, lng: number, index: number): [number, number] {
  const angle = ((index * 53) % 360) * (Math.PI / 180);
  const radius = 0.0032 + (index % 4) * 0.0011;
  return [lat + Math.sin(angle) * radius, lng + Math.cos(angle) * radius];
}

const reports: FieldReport[] = [];
cases.forEach((item) => {
  if (item.status === 'resolved') return;
  reports.push({
    id: `rpt-${item.id}`,
    area: item.area,
    issue: item.issue,
    channel: item.channel,
    lat: item.lat,
    lng: item.lng,
    at: item.createdAt,
    caseId: item.id,
    incidentId: item.incidentId,
  });
});

const kilimani = SERVICE_AREAS.find((area) => area.id === 'kilimani')!;
const southB = SERVICE_AREAS.find((area) => area.id === 'south-b')!;
const [kLat, kLng] = areaCenter(kilimani.polygon);
const [sLat, sLng] = areaCenter(southB.polygon);
const extraIssues = ['Internet Down', 'Slow Internet', 'Connection Unstable'] as const;
const extraChannels = ['whatsapp', 'voice', 'sms', 'ussd'] as const;

for (let index = 0; index < 8; index += 1) {
  const [lat, lng] = jitter(kLat, kLng, index + 3);
  reports.push({
    id: `rpt-k-${index}`,
    area: 'kilimani',
    issue: extraIssues[index % 3],
    channel: extraChannels[index % 4],
    lat,
    lng,
    at: atNairobi(8, 42 + index),
    caseId: 'case-mary',
    incidentId: 'inc-104',
  });
}
for (let index = 0; index < 3; index += 1) {
  const [lat, lng] = jitter(sLat, sLng, index + 2);
  reports.push({
    id: `rpt-s-${index}`,
    area: 'south-b',
    issue: extraIssues[index % 3],
    channel: extraChannels[index % 2],
    lat,
    lng,
    at: atNairobi(7, 20 + index * 4),
    caseId: 'case-fatuma',
    incidentId: 'inc-102',
  });
}

const messages: CommMessage[] = [
  { id: 'msg-1', subscriberId: 'sub-mary', recipientLabel: 'Mary Wanjiku', channel: 'whatsapp', body: 'My internet has been down since morning.', direction: 'inbound', status: 'received', at: rel(2) },
  { id: 'msg-2', subscriberId: 'sub-mary', recipientLabel: 'Mary Wanjiku', channel: 'whatsapp', body: 'There is currently an active service issue affecting your area. Our team is investigating.', direction: 'outbound', status: 'delivered', at: rel(1) },
  { id: 'msg-3', subscriberId: 'sub-james', recipientLabel: 'James Ochieng', channel: 'voice', body: 'Inbound call · customer reported no connection since 8am.', direction: 'inbound', status: 'received', at: rel(16) },
  { id: 'msg-4', subscriberId: 'sub-fatuma', recipientLabel: 'Fatuma Ali', channel: 'ussd', body: '*544# internet status check — service down', direction: 'inbound', status: 'received', at: rel(54) },
  { id: 'msg-5', subscriberId: 'sub-david', recipientLabel: 'David Kipchoge', channel: 'sms', body: 'Speeds are very low this morning.', direction: 'inbound', status: 'received', at: rel(41) },
  { id: 'msg-6', subscriberId: 'sub-samuel', recipientLabel: 'Samuel Kariuki', channel: 'whatsapp', body: 'Office link is slower than usual.', direction: 'inbound', status: 'received', at: rel(95) },
  { id: 'msg-7', subscriberId: 'sub-ann', recipientLabel: 'Ann Wairimu', channel: 'sms', body: 'Payment received. Your Home 20 Mbps plan is active.', direction: 'outbound', status: 'delivered', at: rel(30) },
  { id: 'msg-8', subscriberId: 'sub-lucy', recipientLabel: 'Lucy Akinyi', channel: 'sms', body: 'We tried to reach you about the CBD link. Please reply YES to confirm.', direction: 'outbound', status: 'failed', at: rel(120) },
];

const payments: Payment[] = [
  { id: 'pay-1', subscriberId: 'sub-ann', amount: 2000, method: 'mpesa', at: rel(30), status: 'paid', reference: 'QKJ4H2M8P1' },
  { id: 'pay-2', subscriberId: 'sub-daniel', amount: 8000, method: 'bank', at: rel(50), status: 'paid', reference: 'BNK-88421' },
  { id: 'pay-3', subscriberId: 'sub-samuel', amount: 5000, method: 'mpesa', at: rel(80), status: 'paid', reference: 'QKJ9L1C2A4' },
  { id: 'pay-4', subscriberId: 'sub-peter', amount: 5000, method: 'mpesa', at: rel(110), status: 'paid', reference: 'QKJ2P8D6K3' },
  { id: 'pay-5', subscriberId: 'sub-esther', amount: 2000, method: 'card', at: rel(140), status: 'paid', reference: 'CRD-22918' },
  { id: 'pay-6', subscriberId: 'sub-grace', amount: 2000, method: 'mpesa', at: rel(20), status: 'pending', reference: 'QKJ0W3N7R5' },
  { id: 'pay-7', subscriberId: 'sub-fatuma', amount: 2000, method: 'mpesa', at: rel(35), status: 'pending', reference: 'QKJ7T4B1M9' },
  { id: 'pay-8', subscriberId: 'sub-lucy', amount: 5000, method: 'card', at: rel(200), status: 'failed', reference: 'CRD-11024' },
  { id: 'pay-9', subscriberId: 'sub-aisha', amount: 1500, method: 'mpesa', at: rel(60 * 26), status: 'paid', reference: 'QKJ5E8H2L6' },
  { id: 'pay-10', subscriberId: 'sub-mercy', amount: 1500, method: 'mpesa', at: rel(60 * 20), status: 'paid', reference: 'QKJ1C9Q4Z8' },
];

const notifications: AppNotification[] = [
  { id: 'nt-1', title: 'New outage report in Kilimani', description: 'Mary Wanjiku reported Internet Down on WhatsApp.', at: rel(2), read: false, category: 'outage', link: { kind: 'incident', id: 'inc-104' } },
  { id: 'nt-2', title: '11 customer reports in Kilimani', description: 'Reports are clustered around Kilimani POP. INC-104 is investigating.', at: rel(18), read: false, category: 'outage', link: { kind: 'incident', id: 'inc-104' } },
  { id: 'nt-3', title: 'South B connectivity under monitoring', description: 'INC-102 is affecting 13 subscribers.', at: rel(80), read: false, category: 'outage', link: { kind: 'incident', id: 'inc-102' } },
  { id: 'nt-4', title: 'Payment received', description: 'Ann Wairimu paid KSh 2,000 via M-Pesa.', at: rel(30), read: true, category: 'payment', link: { kind: 'payment', id: 'pay-1' } },
];

const technicians: Technician[] = [
  { id: 'tech-brian', name: 'Brian Kamau', phone: '+254711640228' },
  { id: 'tech-kevin', name: 'Kevin Mwangi', phone: '+254722318904' },
  { id: 'tech-peter', name: 'Peter Otieno', phone: '+254701992145' },
];

const team: TeamMember[] = [
  { id: 'team-amina', name: 'Amina Hassan', role: 'Admin', phone: '+254709220100' },
  { id: 'team-nelly', name: 'Nelly Chebet', role: 'Support Agent', phone: '+254712880441' },
  { id: 'tech-brian', name: 'Brian Kamau', role: 'Technician', phone: '+254711640228' },
  { id: 'tech-kevin', name: 'Kevin Mwangi', role: 'Technician', phone: '+254722318904' },
  { id: 'tech-peter', name: 'Peter Otieno', role: 'Technician', phone: '+254701992145' },
];

const activities: Activity[] = [
  { id: 'act-1', at: rel(2), text: 'Customer report received from WhatsApp' },
  { id: 'act-2', at: atNairobi(8, 47), text: 'Outage detected in Kilimani' },
  { id: 'act-3', at: atNairobi(8, 43), text: '11 customers reported connectivity problems' },
  { id: 'act-4', at: atNairobi(7, 40), text: 'South B connectivity issue placed under monitoring' },
  { id: 'act-5', at: rel(30), text: 'M-Pesa payment recorded for Ann Wairimu' },
  { id: 'act-6', at: rel(150), text: 'Lucy Akinyi case assigned to Nelly Chebet' },
];

const settings: SettingsState = {
  ispName: 'Kijani Networks',
  phone: '+254 709 220 100',
  email: 'noc@kijaninetworks.co.ke',
  location: 'Kilimani, Nairobi',
  notifications: { outage: true, support: true, technician: true, payment: true },
  channels: {
    whatsapp: { connected: true },
    sms: { connected: true },
    voice: { connected: true },
    ussd: { connected: false },
  },
};

const unresolved = cases.filter((item) => item.status !== 'resolved').length;
const high = cases.filter((item) => item.status !== 'resolved' && item.priority === 'high').length;

export function createSeed(): OperationsSnapshot {
  return {
    subscribers,
    cases,
    incidents,
    sites,
    areas: SERVICE_AREAS,
    reports,
    messages,
    plans,
    payments,
    notifications,
    technicians,
    activities,
    team,
    settings,
    census: { active: 1284, online: 1201 },
    hiddenOpenIssues: Math.max(0, 23 - unresolved),
    hiddenAttention: Math.max(0, 8 - high),
    nextIncidentNumber: 110,
  };
}
