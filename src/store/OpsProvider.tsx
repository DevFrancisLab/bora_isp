import { createContext, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react';
import { acknowledgeIncident, assignIncident, createSupportCase, notifyIncident, resolveIncident, simulateOutage as postSimulatedOutage, type SupportCaseInput } from '../services/api';
import { loadOperationsSnapshot } from '../services/snapshot';
import { reducer } from './reducer';
import { initialState, type Action, type OpsState } from './state';

interface OpsContextValue {
  state: OpsState;
  dispatch: (action: Action) => Promise<void>;
  simulateReport: () => Promise<void>;
  simulateOutage: () => Promise<void>;
  reload: () => Promise<void>;
  createCustomerReport: (input: { subscriberId: string; issue: string; source: SupportCaseInput['source']; description: string }) => Promise<string>;
}

const OpsContext = createContext<OpsContextValue | null>(null);

const REPORT_QUEUE = ['Peter Njoroge', 'Aisha Mohammed', 'Ann Wairimu', 'Esther Nyambura', 'Mercy Chebet'];

export function OpsProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, initialState);
  const stateRef = useRef(state);
  stateRef.current = state;
  const reportCursor = useRef(0);
  const timers = useRef<number[]>([]);
  const mutationLock = useRef(false);

  async function createCustomerReport(input: { subscriberId: string; issue: string; source: SupportCaseInput['source']; description: string }) {
    const current = stateRef.current;
    const subscriber = current.subscribers.find((item) => item.id === input.subscriberId);
    const area = current.areas.find((item) => item.id === subscriber?.area);
    if (!subscriber || !area?.remoteId) {
      throw new Error('That subscriber is not available in the operations directory.');
    }
    const internetDown = input.issue === 'Internet Down';
    const created = await createSupportCase({
      subscriber: Number(subscriber.id),
      service_area: area.remoteId,
      category: internetDown ? 'INTERNET_DOWN' : input.issue === 'Slow Internet' ? 'SLOW_INTERNET' : 'TECHNICAL',
      subject: internetDown ? 'Internet Down' : input.issue,
      description: input.description,
      priority: internetDown ? 'HIGH' : 'MEDIUM',
      source: input.source,
    });
    const seed = await loadOperationsSnapshot();
    dispatch({ type: 'HYDRATE', seed });
    dispatch({ type: 'OPEN', dialog: { type: 'case', id: String(created.id) } });
    dispatch({ type: 'TOAST', message: 'Support case created', tone: 'success' });
    return String(created.id);
  }

  async function refreshFromApi() {
    const seed = await loadOperationsSnapshot();
    dispatch({ type: 'HYDRATE', seed });
  }

  async function send(action: Action): Promise<void> {
    if (action.type === 'ACK_INCIDENT' || action.type === 'ASSIGN_INCIDENT' || action.type === 'NOTIFY_INCIDENT' || action.type === 'RESOLVE_INCIDENT') {
      if (mutationLock.current) return;
      mutationLock.current = true;
      try {
        const id = Number(action.id);
        if (action.type === 'ACK_INCIDENT') await acknowledgeIncident(id);
        if (action.type === 'ASSIGN_INCIDENT') await assignIncident(id, Number(action.technicianId));
        if (action.type === 'NOTIFY_INCIDENT') {
          const channels = action.channel === 'both' ? (['WHATSAPP', 'SMS'] as const) : action.channel === 'sms' ? (['SMS'] as const) : (['WHATSAPP'] as const);
          for (const channel of channels) await notifyIncident(id, channel);
        }
        if (action.type === 'RESOLVE_INCIDENT') await resolveIncident(id);
        await refreshFromApi();
        const message = action.type === 'ACK_INCIDENT'
          ? 'Incident acknowledged'
          : action.type === 'ASSIGN_INCIDENT'
            ? 'Technician assigned'
            : action.type === 'NOTIFY_INCIDENT'
              ? 'Notification queued'
              : 'Incident resolved';
        dispatch({ type: 'TOAST', message, tone: 'success' });
        if (action.type === 'ASSIGN_INCIDENT' || action.type === 'RESOLVE_INCIDENT') dispatch({ type: 'CLOSE' });
      } catch (error) {
        dispatch({ type: 'TOAST', message: error instanceof Error ? error.message : 'The ISPBora API request failed.', tone: 'danger' });
        throw error;
      } finally {
        mutationLock.current = false;
      }
      return;
    }
    dispatch(action);
  }

  useEffect(() => {
    let live = true;
    loadOperationsSnapshot()
      .then((seed) => {
        if (live) dispatch({ type: 'HYDRATE', seed });
      })
      .catch(() => {
        if (live) dispatch({ type: 'HYDRATE_ERROR' });
      });
    return () => {
      live = false;
    };
  }, [state.loadAttempt]);

  useEffect(() => {
    if (!state.toasts.length) return;
    const id = state.toasts[0].id;
    const timer = window.setTimeout(() => dispatch({ type: 'DISMISS_TOAST', id }), 3600);
    return () => window.clearTimeout(timer);
  }, [state.toasts]);

  useEffect(() => () => timers.current.forEach((timer) => window.clearTimeout(timer)), []);

  const api = useMemo<OpsContextValue>(
    () => ({
      state,
      dispatch: send,
      createCustomerReport,
      reload: async () => {
        const seed = await loadOperationsSnapshot();
        dispatch({ type: 'HYDRATE', seed });
      },
      simulateReport: async () => {
        const current = stateRef.current;
        const name = REPORT_QUEUE[reportCursor.current % REPORT_QUEUE.length];
        reportCursor.current += 1;
        const subscriber = current.subscribers.find((item) => item.name === name);
        if (!subscriber) {
          dispatch({ type: 'TOAST', message: 'Demo report could not find that subscriber in the loaded directory.', tone: 'warning' });
          return;
        }
        try {
          await createCustomerReport({
            subscriberId: subscriber.id,
            issue: 'Internet Down',
            source: 'WHATSAPP',
            description: `${subscriber.name} reported that internet service is down.`,
          });
        } catch (error) {
          dispatch({ type: 'TOAST', message: error instanceof Error ? error.message : 'The ISPBora API request failed.', tone: 'danger' });
        }
      },
      simulateOutage: async () => {
        if (stateRef.current.simulatingOutage || mutationLock.current) return;
        mutationLock.current = true;
        dispatch({ type: 'SIM_PENDING' });
        try {
          const result = await postSimulatedOutage();
          const seed = await loadOperationsSnapshot();
          dispatch({ type: 'HYDRATE', seed });
          const incident = result.incident;
          if (!incident) {
            dispatch({ type: 'TOAST', message: result.detail || 'Every service area already has an active incident', tone: 'warning' });
            return;
          }
          const area = seed.areas.find((item) => item.remoteId === incident.service_area);
          if (area) dispatch({ type: 'FOCUS_AREA', areaId: area.id });
          dispatch({ type: 'OPEN', dialog: { type: 'incident', id: String(incident.id) } });
          dispatch({
            type: 'TOAST',
            message: result.created
              ? `Outage simulated. ${incident.title} is now investigating.`
              : result.detail || 'Every service area already has an active incident',
            tone: result.created ? 'success' : 'warning',
          });
        } catch (error) {
          dispatch({ type: 'SIM_DONE' });
          dispatch({ type: 'TOAST', message: error instanceof Error ? error.message : 'The ISPBora API request failed.', tone: 'danger' });
        } finally {
          mutationLock.current = false;
        }
      },
    }),
    [state],
  );

  return <OpsContext.Provider value={api}>{children}</OpsContext.Provider>;
}

export function useOps() {
  const context = useContext(OpsContext);
  if (!context) throw new Error('useOps must be used within OpsProvider');
  return context;
}
