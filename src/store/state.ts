import type { AreaId, Channel, OperationsSnapshot, TeamRole } from '../types';

export interface ToastItem {
  id: string;
  message: string;
  tone: 'success' | 'info' | 'warning' | 'danger';
}

export type DialogState =
  | { type: 'search' }
  | { type: 'assign-incident'; id: string }
  | { type: 'notify'; id: string }
  | { type: 'assign-case'; id: string }
  | { type: 'subscriber'; id: string }
  | { type: 'incident'; id: string }
  | { type: 'case'; id: string }
  | { type: 'payment'; id: string }
  | { type: 'site'; id: string }
  | { type: 'add-subscriber' }
  | { type: 'create-case'; subscriberId: string }
  | { type: 'message'; subscriberId?: string }
  | { type: 'plan'; id?: string }
  | { type: 'add-team' }
  | { type: 'suspend'; id: string }
  | null;

export interface OpsState extends OperationsSnapshot {
  status: 'loading' | 'ready' | 'error';
  loadAttempt: number;
  toasts: ToastItem[];
  dialog: DialogState;
  mapFocus: { areaId: AreaId | null; nonce: number };
  prompt: { areaId: AreaId; reports: number } | null;
  simulatingOutage: boolean;
  forcePageError: boolean;
  pageRetry: number;
}

export type Action =
  | { type: 'HYDRATE'; seed: OperationsSnapshot }
  | { type: 'HYDRATE_ERROR' }
  | { type: 'RETRY_BOOT' }
  | { type: 'OPEN'; dialog: Exclude<DialogState, null> }
  | { type: 'CLOSE' }
  | { type: 'TOAST'; message: string; tone?: ToastItem['tone'] }
  | { type: 'DISMISS_TOAST'; id: string }
  | { type: 'MARK_READ'; id: string }
  | { type: 'MARK_ALL_READ' }
  | { type: 'FOCUS_AREA'; areaId: AreaId }
  | { type: 'ACK_INCIDENT'; id: string }
  | { type: 'ASSIGN_INCIDENT'; id: string; technicianId: string }
  | { type: 'NOTIFY_INCIDENT'; id: string; channel: 'whatsapp' | 'sms' | 'both' }
  | { type: 'RESOLVE_INCIDENT'; id: string }
  | { type: 'CUSTOMER_REPORT'; subscriberId: string; issue: string; channel: Channel; reveal?: boolean }
  | { type: 'DECLARE_INCIDENT'; areaId: AreaId }
  | { type: 'DISMISS_PROMPT' }
  | { type: 'SIM_START'; areaId: AreaId }
  | { type: 'ACK_CASE'; id: string }
  | { type: 'ASSIGN_CASE'; id: string; assigneeId: string }
  | { type: 'REPLY_CASE'; id: string; channel: Channel; body: string }
  | { type: 'ESCALATE_CASE'; id: string }
  | { type: 'RESOLVE_CASE'; id: string }
  | { type: 'ADD_SUBSCRIBER'; name: string; phone: string; area: AreaId; packageId: string }
  | { type: 'SUSPEND'; id: string }
  | { type: 'RESTORE'; id: string }
  | { type: 'ACTIVATE'; id: string }
  | { type: 'SEND_MESSAGE'; subscriberId: string; channel: Channel; body: string }
  | { type: 'ADD_PLAN'; name: string; speedMbps: number; priceKes: number; segment: 'Home' | 'Business' }
  | { type: 'UPDATE_PLAN'; id: string; name: string; speedMbps: number; priceKes: number }
  | { type: 'TOGGLE_PLAN'; id: string }
  | { type: 'SAVE_PROFILE'; ispName: string; phone: string; email: string; location: string }
  | { type: 'TOGGLE_SETTING'; key: keyof OpsState['settings']['notifications'] }
  | { type: 'TOGGLE_CHANNEL'; channel: Channel }
  | { type: 'ADD_TEAM'; name: string; role: TeamRole; phone: string }
  | { type: 'FORCE_PAGE_ERROR' }
  | { type: 'CLEAR_PAGE_ERROR' };

export const emptySnapshot = (): OperationsSnapshot => ({
  subscribers: [],
  cases: [],
  incidents: [],
  sites: [],
  areas: [],
  reports: [],
  messages: [],
  plans: [],
  payments: [],
  notifications: [],
  technicians: [],
  activities: [],
  team: [],
  settings: {
    ispName: 'Kijani Networks',
    phone: '',
    email: '',
    location: '',
    notifications: { outage: true, support: true, technician: true, payment: true },
    channels: {
      whatsapp: { connected: true },
      sms: { connected: true },
      voice: { connected: true },
      ussd: { connected: false },
    },
  },
  census: { active: 0, online: 0 },
  hiddenOpenIssues: 0,
  hiddenAttention: 0,
  nextIncidentNumber: 110,
});

export function initialState(): OpsState {
  return {
    ...emptySnapshot(),
    status: 'loading',
    loadAttempt: 0,
    toasts: [],
    dialog: null,
    mapFocus: { areaId: null, nonce: 0 },
    prompt: null,
    simulatingOutage: false,
    forcePageError: false,
    pageRetry: 0,
  };
}
