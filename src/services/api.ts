const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export interface ApiPage<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiSubscriber {
  id: number;
  account_number: string;
  full_name: string;
  phone_number: string;
  email: string;
  address: string;
  service_area: number;
  service_area_name: string;
  plan: string;
  status: 'ACTIVE' | 'SUSPENDED' | 'INACTIVE';
  connection_status: 'ONLINE' | 'OFFLINE' | 'DEGRADED' | 'UNKNOWN';
  installation_date: string;
  created_at: string;
  updated_at: string;
}

export interface ApiSupportCase {
  id: number;
  case_number: string;
  subscriber: number;
  subscriber_name: string;
  category: string;
  subject: string;
  description: string;
  status: string;
  priority: string;
  source: string;
  assigned_to: string;
  service_area: number;
  service_area_name: string;
  possible_outage: boolean;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface ApiIncidentReport {
  id: number;
  incident: number;
  support_case: number | null;
  subscriber: number;
  service_area: number;
  created_at: string;
}

export interface ApiIncident {
  id: number;
  incident_number: string;
  title: string;
  description: string;
  incident_type: string;
  status: 'INVESTIGATING' | 'ACKNOWLEDGED' | 'MONITORING' | 'RESOLVED';
  severity: 'MINOR' | 'MAJOR' | 'CRITICAL';
  service_area: number;
  service_area_name: string;
  affected_subscribers: number;
  report_count: number;
  assigned_technician: number | null;
  assigned_technician_name: string | null;
  started_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  reports: ApiIncidentReport[];
}

export interface ApiServiceArea {
  id: number;
  name: string;
  status: 'OPERATIONAL' | 'DEGRADED' | 'INVESTIGATING' | 'OUTAGE';
  description: string;
  subscriber_count: number;
  geometry: [number, number][];
  created_at: string;
  updated_at: string;
}

export interface ApiNetworkSite {
  id: number;
  name: string;
  site_type: string;
  status: string;
  service_area: number;
  service_area_name: string;
  latitude: string;
  longitude: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface ApiNetworkStatus {
  areas: ApiServiceArea[];
  sites: ApiNetworkSite[];
  active_incidents: number;
}

export interface ApiMessage {
  id: number;
  subscriber: number | null;
  channel: 'WHATSAPP' | 'SMS' | 'VOICE' | 'USSD';
  direction: 'INBOUND' | 'OUTBOUND';
  message_type: string;
  body: string;
  status: 'PENDING' | 'SENT' | 'DELIVERED' | 'FAILED';
  created_at: string;
}

export interface ApiNotification {
  id: number;
  subscriber: number | null;
  incident: number | null;
  channel: 'WHATSAPP' | 'SMS' | 'VOICE' | 'USSD';
  title: string;
  body: string;
  status: 'PENDING' | 'SENT' | 'DELIVERED' | 'FAILED';
  created_at: string;
  sent_at: string | null;
}

export interface ApiActivity {
  id: number;
  text: string;
  created_at: string;
}

export interface ApiDashboardSummary {
  active_subscribers: number;
  online_subscribers: number;
  open_issues: number;
  active_outages: number;
  active_incidents: ApiIncident[];
  recent_support_cases: ApiSupportCase[];
  network_status: ApiServiceArea[];
  recent_activity: ApiActivity[];
}

export interface ApiTechnician {
  id: number;
  name: string;
  phone_number: string;
  email: string;
  status: string;
  service_area: number;
  service_area_name: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError('Unable to load dashboard data. Check that the ISPBora API is running.');
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body === 'string' ? body : JSON.stringify(body);
    } catch {
      detail = response.statusText;
    }
    throw new ApiError(`ISPBora API request failed (${response.status}). ${detail}`, response.status);
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError('The ISPBora API returned a malformed response.');
  }
}

async function getList<T>(path: string): Promise<T[]> {
  const collected: T[] = [];
  let next: string | null = path;
  while (next) {
    const page: ApiPage<T> | T[] = await request<ApiPage<T> | T[]>(next);
    if (Array.isArray(page)) return page;
    if (!page || !Array.isArray(page.results)) throw new ApiError('The ISPBora API returned a malformed response.');
    collected.push(...page.results);
    next = page.next;
  }
  return collected;
}

export const getSubscribers = () => getList<ApiSubscriber>('/api/subscribers/');
export const getSubscriber = (id: number) => request<ApiSubscriber>(`/api/subscribers/${id}/`);
export const getNetworkAreas = () => request<ApiServiceArea[]>('/api/network/areas/');
export const getNetworkSites = () => request<ApiNetworkSite[]>('/api/network/sites/');
export const getNetworkStatus = () => request<ApiNetworkStatus>('/api/network/status/');
export const getSupportCases = () => getList<ApiSupportCase>('/api/support/cases/');
export const getSupportCase = (id: number) => request<ApiSupportCase>(`/api/support/cases/${id}/`);
export const getIncidents = () => getList<ApiIncident>('/api/incidents/');
export const getIncident = (id: number) => request<ApiIncident>(`/api/incidents/${id}/`);
export const getMessages = () => getList<ApiMessage>('/api/messages/');
export const getNotifications = () => getList<ApiNotification>('/api/notifications/');
export const getDashboardSummary = () => request<ApiDashboardSummary>('/api/dashboard/summary/');
export const getTechnicians = () => getList<ApiTechnician>('/api/technicians/');

export const acknowledgeIncident = (id: number) => request<ApiIncident>(`/api/incidents/${id}/acknowledge/`, { method: 'POST' });
export const assignIncident = (id: number, technicianId: number) =>
  request<ApiIncident>(`/api/incidents/${id}/assign/`, { method: 'POST', body: JSON.stringify({ technician_id: technicianId }) });
export const notifyIncident = (id: number, channel: 'WHATSAPP' | 'SMS') =>
  request<{ queued: number }>(`/api/incidents/${id}/notify/`, { method: 'POST', body: JSON.stringify({ channel }) });
export const resolveIncident = (id: number) => request<ApiIncident>(`/api/incidents/${id}/resolve/`, { method: 'POST' });

export function createSubscriber(body: Partial<ApiSubscriber>) {
  return request<ApiSubscriber>('/api/subscribers/', { method: 'POST', body: JSON.stringify(body) });
}

export function updateSubscriber(id: number, body: Partial<ApiSubscriber>) {
  return request<ApiSubscriber>(`/api/subscribers/${id}/`, { method: 'PATCH', body: JSON.stringify(body) });
}

export interface SupportCaseInput {
  subscriber: number;
  service_area: number;
  category: 'INTERNET_DOWN' | 'SLOW_INTERNET' | 'ACCOUNT' | 'BILLING' | 'TECHNICAL' | 'OTHER';
  subject: string;
  description: string;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  source: 'WHATSAPP' | 'VOICE' | 'USSD' | 'SMS' | 'DASHBOARD' | 'PHONE';
}

export interface SimulatedOutage {
  created: boolean;
  detail: string;
  incident: ApiIncident | null;
}

export function simulateOutage() {
  return request<SimulatedOutage>('/api/incidents/simulate/', { method: 'POST', body: JSON.stringify({}) });
}

export function createSupportCase(body: SupportCaseInput) {
  return request<ApiSupportCase>('/api/support/cases/', { method: 'POST', body: JSON.stringify(body) });
}

export function updateSupportCase(id: number, body: Record<string, unknown>) {
  return request<ApiSupportCase>(`/api/support/cases/${id}/`, { method: 'PATCH', body: JSON.stringify(body) });
}

export interface AssistantAction {
  type: string;
  label: string;
  status: 'success' | 'failed' | 'unavailable' | 'queued';
}

export interface AssistantReply {
  reply: string;
  actions: AssistantAction[];
}

export interface AssistantHistoryTurn {
  role: 'operator' | 'assistant';
  content: string;
}

export interface AssistantRequest {
  message: string;
  channel?: 'dashboard' | 'whatsapp' | 'sms' | 'ussd' | 'voice';
  context?: { subscriber_id?: number };
  history?: AssistantHistoryTurn[];
}

export function askAssistant(body: AssistantRequest) {
  return request<AssistantReply>('/api/ai/assistant/', { method: 'POST', body: JSON.stringify({ channel: 'dashboard', ...body }) });
}

export function assistantErrorMessage(error: unknown) {
  if (!(error instanceof ApiError)) return 'The AI assistant is unavailable.';
  const match = error.message.match(/"detail"\s*:\s*"([^"]+)"/);
  if (match) return match[1];
  if (error.status === 503) return 'The AI assistant is temporarily unavailable.';
  if (error.message.includes('Unable to load dashboard data')) return 'The ISPBora API is not running.';
  return 'The AI assistant could not answer that request.';
}
