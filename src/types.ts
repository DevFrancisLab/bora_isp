export type AreaId = 'kilimani' | 'south-b' | 'lavington' | 'kilimani-west' | 'cbd';

export type Channel = 'whatsapp' | 'voice' | 'ussd' | 'sms';

export type SubscriberStatus = 'active' | 'suspended' | 'pending';
export type ConnectionState = 'online' | 'offline' | 'unstable';
export type PaymentStatus = 'paid' | 'pending' | 'overdue';
export type CaseStatus = 'open' | 'investigating' | 'assigned' | 'resolved';
export type Priority = 'high' | 'medium' | 'low';
export type IncidentStatus = 'investigating' | 'acknowledged' | 'assigned' | 'monitoring' | 'resolved';
export type Severity = 'critical' | 'warning' | 'info';
export type AreaHealth = 'operational' | 'degraded' | 'outage';
export type PayMethod = 'mpesa' | 'bank' | 'card';
export type TxnStatus = 'paid' | 'pending' | 'failed';
export type TeamRole = 'Admin' | 'Support Agent' | 'Technician';

export interface Subscriber {
  id: string;
  accountId: string;
  name: string;
  phone: string;
  area: AreaId;
  packageId: string;
  status: SubscriberStatus;
  connection: ConnectionState;
  lastSeen: string;
  paymentStatus: PaymentStatus;
  balance: number;
  offlineDueToIncidentId?: string;
}

export interface ConversationMessage {
  id: string;
  sender: 'customer' | 'agent' | 'system';
  body: string;
  channel?: Channel;
  at: string;
}

export interface SupportCase {
  id: string;
  subscriberId: string;
  issue: string;
  channel: Channel;
  area: AreaId;
  priority: Priority;
  status: CaseStatus;
  createdAt: string;
  lat: number;
  lng: number;
  incidentId?: string;
  assigneeId?: string;
  escalated?: boolean;
  messages: ConversationMessage[];
}

export interface TimelineEvent {
  id: string;
  at: string;
  text: string;
}

export interface Incident {
  id: string;
  code: string;
  title: string;
  area: AreaId;
  siteId: string;
  status: IncidentStatus;
  severity: Severity;
  affectedSubscribers: number;
  reportCount: number;
  startedAt: string;
  resolvedAt?: string;
  technicianId?: string;
  notified?: { channel: 'whatsapp' | 'sms' | 'both'; at: string };
  timeline: TimelineEvent[];
}

export interface NetworkSite {
  id: string;
  name: string;
  areaIds: AreaId[];
  lat: number;
  lng: number;
  served: number;
  openIssueBaseline: number;
  openIssueSnapshot: number;
}

export interface ServiceArea {
  id: AreaId;
  name: string;
  polygon: [number, number][];
}

export interface FieldReport {
  id: string;
  area: AreaId;
  issue: string;
  channel: Channel;
  lat: number;
  lng: number;
  at: string;
  caseId?: string;
  incidentId?: string;
}

export interface CommMessage {
  id: string;
  subscriberId?: string;
  recipientLabel: string;
  channel: Channel;
  body: string;
  direction: 'inbound' | 'outbound';
  status: 'delivered' | 'sent' | 'failed' | 'received';
  at: string;
  broadcast?: boolean;
}

export interface Plan {
  id: string;
  name: string;
  speedMbps: number;
  priceKes: number;
  segment: 'Home' | 'Business';
  active: boolean;
}

export interface Payment {
  id: string;
  subscriberId: string;
  amount: number;
  method: PayMethod;
  at: string;
  status: TxnStatus;
  reference: string;
}

export type NotifLink =
  | { kind: 'incident'; id: string }
  | { kind: 'case'; id: string }
  | { kind: 'subscriber'; id: string }
  | { kind: 'payment'; id: string }
  | { kind: 'route'; to: string };

export interface AppNotification {
  id: string;
  title: string;
  description: string;
  at: string;
  read: boolean;
  link: NotifLink;
  category: 'outage' | 'support' | 'technician' | 'payment';
}

export interface Technician {
  id: string;
  name: string;
  phone: string;
}

export interface Activity {
  id: string;
  at: string;
  text: string;
}

export interface TeamMember {
  id: string;
  name: string;
  role: TeamRole;
  phone: string;
}

export interface SettingsState {
  ispName: string;
  phone: string;
  email: string;
  location: string;
  notifications: {
    outage: boolean;
    support: boolean;
    technician: boolean;
    payment: boolean;
  };
  channels: Record<Channel, { connected: boolean }>;
}

export interface OperationsSnapshot {
  subscribers: Subscriber[];
  cases: SupportCase[];
  incidents: Incident[];
  sites: NetworkSite[];
  areas: ServiceArea[];
  reports: FieldReport[];
  messages: CommMessage[];
  plans: Plan[];
  payments: Payment[];
  notifications: AppNotification[];
  technicians: Technician[];
  activities: Activity[];
  team: TeamMember[];
  settings: SettingsState;
  census: { active: number; online: number };
  hiddenOpenIssues: number;
  hiddenAttention: number;
  nextIncidentNumber: number;
}
