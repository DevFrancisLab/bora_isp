import { AREA_LABEL } from '../domain/labels';
import { AREA_SHARE, AREA_SITE } from '../domain/network';
import { uid } from '../domain/format';
import type { AreaId, Channel, Incident, Subscriber, SupportCase } from '../types';
import type { Action, OpsState, ToastItem } from './state';

const nowIso = () => new Date().toISOString();

function toast(state: OpsState, message: string, tone: ToastItem['tone'] = 'success'): OpsState {
  return { ...state, toasts: [...state.toasts.slice(-3), { id: uid('toast'), message, tone }] };
}

function activity(state: OpsState, text: string): OpsState {
  return { ...state, activities: [{ id: uid('act'), at: nowIso(), text }, ...state.activities].slice(0, 40) };
}

function note(
  state: OpsState,
  category: OpsState['notifications'][number]['category'],
  title: string,
  description: string,
  link: OpsState['notifications'][number]['link'],
): OpsState {
  if (!state.settings.notifications[category]) return state;
  return {
    ...state,
    notifications: [
      { id: uid('nt'), title, description, at: nowIso(), read: false, category, link },
      ...state.notifications,
    ].slice(0, 30),
  };
}

function stamp(
  state: OpsState,
  extras: {
    activity?: string;
    toast?: string;
    tone?: ToastItem['tone'];
    note?: { category: OpsState['notifications'][number]['category']; title: string; description: string; link: OpsState['notifications'][number]['link'] };
  },
): OpsState {
  let next = state;
  if (extras.activity) next = activity(next, extras.activity);
  if (extras.note) next = note(next, extras.note.category, extras.note.title, extras.note.description, extras.note.link);
  if (extras.toast) next = toast(next, extras.toast, extras.tone);
  return next;
}

function siteIndex(state: OpsState, area: AreaId) {
  return state.sites.findIndex((site) => site.id === AREA_SITE[area]);
}

function patchSub(state: OpsState, id: string, fn: (subscriber: Subscriber) => Subscriber): OpsState {
  return { ...state, subscribers: state.subscribers.map((subscriber) => (subscriber.id === id ? fn(subscriber) : subscriber)) };
}

export function reducer(state: OpsState, action: Action): OpsState {
  switch (action.type) {
    case 'HYDRATE':
      return {
        ...state,
        ...action.seed,
        status: 'ready',
        toasts: state.toasts,
        dialog: state.dialog,
        forcePageError: state.forcePageError,
        pageRetry: state.pageRetry,
        simulatingOutage: false,
      };
    case 'HYDRATE_ERROR':
      return { ...state, status: 'error' };
    case 'RETRY_BOOT':
      return { ...state, status: 'loading', loadAttempt: state.loadAttempt + 1 };
    case 'OPEN':
      return { ...state, dialog: action.dialog };
    case 'CLOSE':
      return { ...state, dialog: null };
    case 'TOAST':
      return toast(state, action.message, action.tone);
    case 'DISMISS_TOAST':
      return { ...state, toasts: state.toasts.filter((item) => item.id !== action.id) };
    case 'MARK_READ':
      return {
        ...state,
        notifications: state.notifications.map((item) => (item.id === action.id ? { ...item, read: true } : item)),
      };
    case 'MARK_ALL_READ':
      return { ...state, notifications: state.notifications.map((item) => ({ ...item, read: true })) };
    case 'FOCUS_AREA':
      return { ...state, mapFocus: { areaId: action.areaId, nonce: state.mapFocus.nonce + 1 } };
    case 'FORCE_PAGE_ERROR':
      return toast({ ...state, forcePageError: true }, 'Page load failed. Use Retry on this screen.', 'warning');
    case 'CLEAR_PAGE_ERROR':
      return { ...state, forcePageError: false, pageRetry: state.pageRetry + 1 };
    case 'DISMISS_PROMPT':
      return { ...state, prompt: null };
    case 'SIM_START':
      return stamp(
        { ...state, simulatingOutage: true, mapFocus: { areaId: action.areaId, nonce: state.mapFocus.nonce + 1 } },
        { activity: `Multiple customer reports arriving in ${AREA_LABEL[action.areaId]}`, toast: `Customer reports arriving in ${AREA_LABEL[action.areaId]}`, tone: 'warning' },
      );
    case 'ACK_INCIDENT': {
      const incident = state.incidents.find((item) => item.id === action.id);
      if (!incident || incident.status === 'resolved') return toast(state, 'Incident is already resolved', 'warning');
      if (incident.status === 'acknowledged' || incident.status === 'assigned') return toast(state, 'Incident already acknowledged', 'info');
      const at = nowIso();
      return stamp(
        {
          ...state,
          incidents: state.incidents.map((item) =>
            item.id === action.id
              ? { ...item, status: 'acknowledged', timeline: [...item.timeline, { id: uid('tl'), at, text: 'ISP acknowledged incident' }] }
              : item,
          ),
        },
        {
          activity: `${incident.code} acknowledged`,
          toast: 'Incident acknowledged',
          note: { category: 'outage', title: `${incident.code} acknowledged`, description: incident.title, link: { kind: 'incident', id: incident.id } },
        },
      );
    }
    case 'ASSIGN_INCIDENT': {
      const incident = state.incidents.find((item) => item.id === action.id);
      const tech = state.technicians.find((item) => item.id === action.technicianId);
      if (!incident || !tech || incident.status === 'resolved') return state;
      const at = nowIso();
      return stamp(
        {
          ...state,
          dialog: null,
          incidents: state.incidents.map((item) =>
            item.id === action.id
              ? {
                  ...item,
                  status: 'assigned',
                  technicianId: tech.id,
                  timeline: [...item.timeline, { id: uid('tl'), at, text: `Technician assigned · ${tech.name}` }],
                }
              : item,
          ),
        },
        {
          activity: `Technician assigned to ${incident.code}`,
          toast: 'Technician assigned',
          note: {
            category: 'technician',
            title: `Technician assigned to ${incident.code}`,
            description: `${tech.name} is assigned to ${incident.title}.`,
            link: { kind: 'incident', id: incident.id },
          },
        },
      );
    }
    case 'NOTIFY_INCIDENT': {
      const incident = state.incidents.find((item) => item.id === action.id);
      if (!incident || incident.status === 'resolved') return toast(state, 'Incident is already resolved', 'warning');
      const channelOk =
        action.channel === 'both'
          ? state.settings.channels.whatsapp.connected || state.settings.channels.sms.connected
          : state.settings.channels[action.channel].connected;
      if (!channelOk) return toast(state, 'Selected channel is disconnected. Reconnect it in Settings.', 'warning');
      const at = nowIso();
      const label = action.channel === 'both' ? 'WhatsApp and SMS' : action.channel === 'whatsapp' ? 'WhatsApp' : 'SMS';
      const body = `${state.settings.ispName}: We are investigating a service disruption in ${AREA_LABEL[incident.area]}. Our team is working to restore your connection. Ref ${incident.code}.`;
      const linked = state.cases.map((item) =>
        item.incidentId === incident.id && item.status !== 'resolved'
          ? { ...item, messages: [...item.messages, { id: uid('cm'), sender: 'agent' as const, body: `Outage notice sent on ${label}.`, at, channel: action.channel === 'sms' ? 'sms' as const : 'whatsapp' as const }] }
          : item,
      );
      return stamp(
        {
          ...state,
          dialog: { type: 'notify', id: incident.id },
          cases: linked,
          incidents: state.incidents.map((item) =>
            item.id === incident.id
              ? { ...item, notified: { channel: action.channel, at }, timeline: [...item.timeline, { id: uid('tl'), at, text: `Customers notified via ${label}` }] }
              : item,
          ),
          messages: [
            {
              id: uid('msg'),
              recipientLabel: `${incident.affectedSubscribers} subscribers · ${AREA_LABEL[incident.area]}`,
              channel: action.channel === 'sms' ? 'sms' : 'whatsapp',
              body,
              direction: 'outbound',
              status: 'sent',
              at,
              broadcast: true,
            },
            ...state.messages,
          ],
        },
        {
          activity: `${incident.affectedSubscribers} customers notified for ${incident.code}`,
          toast: 'Customers notified',
          note: {
            category: 'outage',
            title: `${incident.affectedSubscribers} customers received outage notification`,
            description: `${label} · ${incident.code}`,
            link: { kind: 'incident', id: incident.id },
          },
        },
      );
    }
    case 'RESOLVE_INCIDENT': {
      const incident = state.incidents.find((item) => item.id === action.id);
      if (!incident || incident.status === 'resolved') return toast(state, 'Incident is already resolved', 'info');
      const at = nowIso();
      let onlineGain = 0;
      const subscribers = state.subscribers.map((subscriber) => {
        if (subscriber.offlineDueToIncidentId === incident.id && subscriber.status === 'active') {
          onlineGain += 1;
          return { ...subscriber, connection: 'online' as const, offlineDueToIncidentId: undefined, lastSeen: at };
        }
        return subscriber;
      });
      const areaName = AREA_LABEL[incident.area];
      const restoreBody = `${state.settings.ispName}: Service in ${areaName} has been restored. Thank you for your patience. Ref ${incident.code}.`;
      return stamp(
        {
          ...state,
          dialog: state.dialog?.type === 'incident' ? state.dialog : null,
          subscribers,
          census: { ...state.census, online: state.census.online + onlineGain },
          simulatingOutage: false,
          cases: state.cases.map((item) =>
            item.incidentId === incident.id
              ? { ...item, messages: [...item.messages, { id: uid('cm'), sender: 'system' as const, body: `Network service restored in ${areaName}. Restoration notice sent to the customer.`, at }] }
              : item,
          ),
          incidents: state.incidents.map((item) =>
            item.id === incident.id
              ? { ...item, status: 'resolved', resolvedAt: at, timeline: [...item.timeline, { id: uid('tl'), at, text: 'Incident resolved. Restoration notice sent.' }] }
              : item,
          ),
          messages: [
            {
              id: uid('msg'),
              recipientLabel: `${incident.affectedSubscribers} subscribers · ${areaName}`,
              channel: 'whatsapp',
              body: restoreBody,
              direction: 'outbound',
              status: 'sent',
              at,
              broadcast: true,
            },
            ...state.messages,
          ],
        },
        {
          activity: `Network restored in ${areaName}`,
          toast: 'Incident resolved. Customers notified of restoration.',
          note: { category: 'outage', title: `Network restored in ${areaName}`, description: `${incident.code} is resolved.`, link: { kind: 'incident', id: incident.id } },
        },
      );
    }
    case 'CUSTOMER_REPORT':
      return addReport(state, action.subscriberId, action.issue, action.channel, action.reveal);
    case 'DECLARE_INCIDENT':
      return declareIncident(state, action.areaId);
    case 'ACK_CASE': {
      const supportCase = state.cases.find((item) => item.id === action.id);
      if (!supportCase || supportCase.status === 'resolved') return state;
      if (supportCase.status !== 'open') return toast(state, 'Support case already acknowledged', 'info');
      const at = nowIso();
      return stamp(updateCase(state, action.id, (item) => ({ ...item, status: 'investigating', messages: [...item.messages, { id: uid('cm'), sender: 'system', body: 'Case acknowledged by NOC.', at }] })), {
        activity: `Support case acknowledged · ${supportCase.issue}`,
        toast: 'Support case acknowledged',
      });
    }
    case 'ASSIGN_CASE': {
      const supportCase = state.cases.find((item) => item.id === action.id);
      const member = state.team.find((item) => item.id === action.assigneeId) ?? state.technicians.find((item) => item.id === action.assigneeId);
      if (!supportCase || !member || supportCase.status === 'resolved') return state;
      const at = nowIso();
      const name = member.name;
      return stamp(
        {
          ...updateCase(state, action.id, (item) => ({
            ...item,
            status: 'assigned',
            assigneeId: action.assigneeId,
            messages: [...item.messages, { id: uid('cm'), sender: 'system', body: `Assigned to ${name}.`, at }],
          })),
          dialog: null,
        },
        { activity: `${supportCase.issue} assigned to ${name}`, toast: 'Support case assigned', note: { category: 'support', title: 'Support case assigned', description: `${name} · ${supportCase.issue}`, link: { kind: 'case', id: supportCase.id } } },
      );
    }
    case 'REPLY_CASE': {
      const supportCase = state.cases.find((item) => item.id === action.id);
      if (!supportCase) return state;
      if (!state.settings.channels[action.channel].connected) return toast(state, `${action.channel.toUpperCase()} is disconnected. Reconnect it in Settings.`, 'warning');
      const at = nowIso();
      const subscriber = state.subscribers.find((item) => item.id === supportCase.subscriberId);
      return stamp(
        {
          ...updateCase(state, action.id, (item) => ({
            ...item,
            messages: [...item.messages, { id: uid('cm'), sender: 'agent', body: action.body, at, channel: action.channel }],
          })),
          messages: [
            { id: uid('msg'), subscriberId: supportCase.subscriberId, recipientLabel: subscriber?.name ?? 'Customer', channel: action.channel, body: action.body, direction: 'outbound', status: 'sent', at },
            ...state.messages,
          ],
        },
        { toast: 'Message sent' },
      );
    }
    case 'ESCALATE_CASE': {
      const supportCase = state.cases.find((item) => item.id === action.id);
      if (!supportCase || supportCase.status === 'resolved') return state;
      const at = nowIso();
      let next = updateCase(state, action.id, (item) => ({
        ...item,
        priority: 'high',
        escalated: true,
        status: item.status === 'open' ? 'investigating' : item.status,
        messages: [...item.messages, { id: uid('cm'), sender: 'system', body: 'Escalated to network operations.', at }],
      }));
      const openInArea = next.cases.filter((item) => item.area === supportCase.area && item.status !== 'resolved').length;
      const hasIncident = next.incidents.some((item) => item.area === supportCase.area && item.status !== 'resolved');
      next = stamp(next, {
        activity: `Support case escalated in ${AREA_LABEL[supportCase.area]}`,
        toast: 'Support case escalated',
        note: { category: 'support', title: 'Support case escalated', description: `${supportCase.issue} · ${AREA_LABEL[supportCase.area]}`, link: { kind: 'case', id: supportCase.id } },
      });
      if (!hasIncident && openInArea >= 3) {
        next = { ...next, prompt: { areaId: supportCase.area, reports: openInArea } };
      }
      return next;
    }
    case 'RESOLVE_CASE': {
      const supportCase = state.cases.find((item) => item.id === action.id);
      if (!supportCase || supportCase.status === 'resolved') return toast(state, 'Support case already resolved', 'info');
      const at = nowIso();
      return stamp(
        updateCase(state, action.id, (item) => ({
          ...item,
          status: 'resolved',
          messages: [...item.messages, { id: uid('cm'), sender: 'system', body: 'Case marked resolved.', at }],
        })),
        { activity: `Support case resolved · ${supportCase.issue}`, toast: 'Support case resolved' },
      );
    }
    case 'ADD_SUBSCRIBER': {
      const id = uid('sub');
      const subscriber: Subscriber = {
        id,
        accountId: `SUB-${String(10000 + state.subscribers.length).slice(-5)}`,
        name: action.name.trim(),
        phone: action.phone.trim(),
        area: action.area,
        packageId: action.packageId,
        status: 'pending',
        connection: 'offline',
        lastSeen: nowIso(),
        paymentStatus: 'pending',
        balance: 0,
      };
      return stamp({ ...state, subscribers: [subscriber, ...state.subscribers], dialog: { type: 'subscriber', id } }, { toast: 'Subscriber added', activity: `${subscriber.name} added as a pending subscriber` });
    }
    case 'SUSPEND':
      return changeAccess(state, action.id, 'suspend');
    case 'RESTORE':
      return changeAccess(state, action.id, 'restore');
    case 'ACTIVATE':
      return changeAccess(state, action.id, 'activate');
    case 'SEND_MESSAGE': {
      if (!state.settings.channels[action.channel].connected) {
        return toast(state, 'That channel is disconnected. Reconnect it in Settings.', 'warning');
      }
      const subscriber = state.subscribers.find((item) => item.id === action.subscriberId);
      if (!subscriber) return state;
      const at = nowIso();
      return stamp(
        {
          ...state,
          dialog: null,
          messages: [
            { id: uid('msg'), subscriberId: subscriber.id, recipientLabel: subscriber.name, channel: action.channel, body: action.body, direction: 'outbound', status: 'sent', at },
            ...state.messages,
          ],
        },
        { toast: 'Message sent', activity: `Message sent to ${subscriber.name}` },
      );
    }
    case 'ADD_PLAN': {
      const plan = { id: uid('plan'), name: action.name.trim(), speedMbps: action.speedMbps, priceKes: action.priceKes, segment: action.segment, active: true };
      return stamp({ ...state, plans: [...state.plans, plan], dialog: null }, { toast: 'Plan created' });
    }
    case 'UPDATE_PLAN':
      return stamp(
        {
          ...state,
          dialog: null,
          plans: state.plans.map((plan) => (plan.id === action.id ? { ...plan, name: action.name.trim(), speedMbps: action.speedMbps, priceKes: action.priceKes } : plan)),
        },
        { toast: 'Plan updated' },
      );
    case 'TOGGLE_PLAN': {
      const plan = state.plans.find((item) => item.id === action.id);
      if (!plan) return state;
      const active = !plan.active;
      return stamp(
        { ...state, plans: state.plans.map((item) => (item.id === plan.id ? { ...item, active } : item)) },
        { toast: active ? 'Plan activated' : 'Plan deactivated' },
      );
    }
    case 'SAVE_PROFILE':
      return stamp(
        { ...state, settings: { ...state.settings, ispName: action.ispName, phone: action.phone, email: action.email, location: action.location } },
        { toast: 'Settings saved' },
      );
    case 'TOGGLE_SETTING':
      return stamp(
        { ...state, settings: { ...state.settings, notifications: { ...state.settings.notifications, [action.key]: !state.settings.notifications[action.key] } } },
        { toast: 'Settings saved' },
      );
    case 'TOGGLE_CHANNEL': {
      const connected = !state.settings.channels[action.channel].connected;
      const label = action.channel === 'whatsapp' ? 'WhatsApp' : action.channel.toUpperCase() === 'SMS' ? 'SMS' : action.channel === 'voice' ? 'Voice' : 'USSD';
      return stamp(
        { ...state, settings: { ...state.settings, channels: { ...state.settings.channels, [action.channel]: { connected } } } },
        { toast: `${label} ${connected ? 'connected' : 'disconnected'}` },
      );
    }
    case 'ADD_TEAM': {
      const id = uid('team');
      const member = { id, name: action.name.trim(), role: action.role, phone: action.phone.trim() };
      const technicians = action.role === 'Technician' ? [...state.technicians, { id, name: member.name, phone: member.phone }] : state.technicians;
      return stamp({ ...state, team: [...state.team, member], technicians, dialog: null }, { toast: 'Team member added' });
    }
    default:
      return state;
  }
}

function updateCase(state: OpsState, id: string, fn: (item: SupportCase) => SupportCase): OpsState {
  return { ...state, cases: state.cases.map((item) => (item.id === id ? fn(item) : item)) };
}

function addReport(state: OpsState, subscriberId: string, issue: string, channel: Channel, reveal?: boolean): OpsState {
  const subscriber = state.subscribers.find((item) => item.id === subscriberId);
  if (!subscriber) return state;
  const at = nowIso();
  const supportCase: SupportCase = {
    id: uid('case'),
    subscriberId,
    issue,
    channel,
    area: subscriber.area,
    priority: issue === 'Internet Down' ? 'high' : 'medium',
    status: 'open',
    createdAt: at,
    lat: subscriberLat(state, subscriber.area),
    lng: subscriberLng(state, subscriber.area),
    messages: [{ id: uid('cm'), sender: 'customer', body: reportBody(issue), at, channel }],
  };
  const incident = state.incidents.find((item) => item.area === subscriber.area && item.status !== 'resolved');
  if (incident) supportCase.incidentId = incident.id;
  let next: OpsState = {
    ...state,
    cases: [supportCase, ...state.cases],
    reports: [
      { id: uid('rpt'), area: subscriber.area, issue, channel, lat: supportCase.lat, lng: supportCase.lng, at, caseId: supportCase.id, incidentId: incident?.id },
      ...state.reports,
    ],
    messages: [
      { id: uid('msg'), subscriberId, recipientLabel: subscriber.name, channel, body: reportBody(issue), direction: 'inbound', status: 'received', at },
      ...state.messages,
    ],
  };
  if (subscriber.connection === 'online' && subscriber.status === 'active') {
    next = patchSub(next, subscriber.id, (item) => ({
      ...item,
      connection: 'offline',
      lastSeen: at,
      offlineDueToIncidentId: incident?.id ?? `pending:${subscriber.area}`,
    }));
    next = { ...next, census: { ...next.census, online: next.census.online - 1 } };
  } else {
    next = patchSub(next, subscriber.id, (item) => ({ ...item, lastSeen: at }));
  }
  if (incident) {
    next = {
      ...next,
      incidents: next.incidents.map((item) => (item.id === incident.id ? { ...item, reportCount: item.reportCount + 1 } : item)),
    };
  }
  const areaName = AREA_LABEL[subscriber.area];
  if (reveal) next = { ...next, dialog: { type: 'case', id: supportCase.id } };
  return stamp(next, {
    activity: `Customer report received from ${channel === 'whatsapp' ? 'WhatsApp' : channel === 'voice' ? 'Voice' : channel.toUpperCase()}`,
    toast: 'Customer report received',
    note: {
      category: incident ? 'outage' : 'support',
      title: `New ${incident ? 'outage report' : 'customer report'} in ${areaName}`,
      description: `${subscriber.name} · ${issue}`,
      link: incident ? { kind: 'incident', id: incident.id } : { kind: 'case', id: supportCase.id },
    },
  });
}

function declareIncident(state: OpsState, areaId: AreaId): OpsState {
  const existing = state.incidents.find((item) => item.area === areaId && item.status !== 'resolved');
  if (existing) {
    return stamp(
      { ...state, simulatingOutage: false, dialog: { type: 'incident', id: existing.id }, mapFocus: { areaId, nonce: state.mapFocus.nonce + 1 } },
      { toast: 'An incident is already open in this area', tone: 'info' },
    );
  }
  const at = nowIso();
  const areaCases = state.cases.filter((item) => item.area === areaId && item.status !== 'resolved');
  const site = state.sites.find((item) => item.id === AREA_SITE[areaId]);
  const affected = Math.max(12, Math.round((site?.served ?? 200) * AREA_SHARE[areaId] * 0.08));
  const number = state.nextIncidentNumber;
  const incident: Incident = {
    id: uid('inc'),
    code: `INC-${number}`,
    title: `${AREA_LABEL[areaId]} Service Disruption`,
    area: areaId,
    siteId: AREA_SITE[areaId],
    status: 'investigating',
    severity: 'critical',
    affectedSubscribers: affected,
    reportCount: Math.max(areaCases.length, 1),
    startedAt: at,
    timeline: [
      { id: uid('tl'), at: areaCases[0]?.createdAt ?? at, text: 'First customer report received' },
      { id: uid('tl'), at, text: 'Multiple nearby reports detected' },
      { id: uid('tl'), at, text: 'Incident created' },
    ],
  };
  const pendingKey = `pending:${areaId}`;
  return stamp(
    {
      ...state,
      nextIncidentNumber: number + 1,
      simulatingOutage: false,
      prompt: null,
      incidents: [incident, ...state.incidents],
      cases: state.cases.map((item) => (item.area === areaId && item.status !== 'resolved' ? { ...item, incidentId: incident.id } : item)),
      reports: state.reports.map((item) => (item.area === areaId ? { ...item, incidentId: incident.id } : item)),
      subscribers: state.subscribers.map((item) => (item.offlineDueToIncidentId === pendingKey ? { ...item, offlineDueToIncidentId: incident.id } : item)),
      mapFocus: { areaId, nonce: state.mapFocus.nonce + 1 },
    },
    {
      activity: `Outage detected in ${AREA_LABEL[areaId]}`,
      toast: `Possible outage declared in ${AREA_LABEL[areaId]}`,
      tone: 'warning',
      note: {
        category: 'outage',
        title: `New outage in ${AREA_LABEL[areaId]}`,
        description: `${incident.code} · ${affected} subscribers affected`,
        link: { kind: 'incident', id: incident.id },
      },
    },
  );
}

function changeAccess(state: OpsState, id: string, mode: 'suspend' | 'restore' | 'activate'): OpsState {
  const subscriber = state.subscribers.find((item) => item.id === id);
  if (!subscriber) return state;
  const index = siteIndex(state, subscriber.area);
  const sites = state.sites.map((site) => ({ ...site }));
  let census = { ...state.census };
  let nextSub = { ...subscriber };
  if (mode === 'suspend' && subscriber.status === 'active') {
    census.active -= 1;
    if (subscriber.connection === 'online') census.online -= 1;
    if (index >= 0) sites[index].served -= 1;
    nextSub = { ...nextSub, status: 'suspended', connection: 'offline', offlineDueToIncidentId: undefined };
  } else if ((mode === 'restore' && subscriber.status === 'suspended') || (mode === 'activate' && subscriber.status === 'pending')) {
    census.active += 1;
    census.online += 1;
    if (index >= 0) sites[index].served += 1;
    nextSub = { ...nextSub, status: 'active', connection: 'online', lastSeen: nowIso(), offlineDueToIncidentId: undefined };
  } else {
    return toast(state, 'Subscriber status is unchanged', 'info');
  }
  return stamp(
    { ...patchSub({ ...state, sites, census, dialog: { type: 'subscriber', id } }, id, () => nextSub) },
    { toast: 'Subscriber updated', activity: `${subscriber.name} service ${mode === 'suspend' ? 'suspended' : 'restored'}` },
  );
}

function subscriberLat(state: OpsState, area: AreaId) {
  const match = state.areas.find((item) => item.id === area);
  if (!match) return -1.292;
  const lat = match.polygon.reduce((sum, point) => sum + point[0], 0) / match.polygon.length;
  return lat + (Math.random() - 0.5) * 0.006;
}

function subscriberLng(state: OpsState, area: AreaId) {
  const match = state.areas.find((item) => item.id === area);
  if (!match) return 36.8;
  const lng = match.polygon.reduce((sum, point) => sum + point[1], 0) / match.polygon.length;
  return lng + (Math.random() - 0.5) * 0.006;
}

function reportBody(issue: string) {
  if (issue === 'Internet Down') return 'My internet is not working.';
  if (issue === 'Slow Internet') return 'The connection is very slow.';
  return 'The connection keeps dropping.';
}
