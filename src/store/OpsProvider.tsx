import { createContext, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react';
import { loadOperationsSnapshot } from '../services/snapshot';
import type { AreaId } from '../types';
import { reducer } from './reducer';
import { initialState, type Action, type OpsState } from './state';

interface OpsContextValue {
  state: OpsState;
  dispatch: (action: Action) => void;
  simulateReport: () => void;
  simulateOutage: () => void;
}

const OpsContext = createContext<OpsContextValue | null>(null);

const REPORT_QUEUE: { subscriberId: string; issue: string }[] = [
  { subscriberId: 'sub-peter', issue: 'Internet Down' },
  { subscriberId: 'sub-aisha', issue: 'Connection Unstable' },
  { subscriberId: 'sub-ann', issue: 'Slow Internet' },
  { subscriberId: 'sub-esther', issue: 'Internet Down' },
  { subscriberId: 'sub-mercy', issue: 'Slow Internet' },
];

export function OpsProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, initialState);
  const stateRef = useRef(state);
  stateRef.current = state;
  const reportCursor = useRef(0);
  const timers = useRef<number[]>([]);

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
      dispatch,
      simulateReport: () => {
        const template = REPORT_QUEUE[reportCursor.current % REPORT_QUEUE.length];
        reportCursor.current += 1;
        dispatch({ type: 'CUSTOMER_REPORT', subscriberId: template.subscriberId, issue: template.issue, channel: 'whatsapp' });
      },
      simulateOutage: () => {
        const current = stateRef.current;
        if (current.simulatingOutage) return;
        const busy = new Set(current.incidents.filter((item) => item.status !== 'resolved').map((item) => item.area));
        const area = current.areas.find((item) => !busy.has(item.id));
        if (!area) {
          dispatch({ type: 'TOAST', message: 'Every service area already has an active incident', tone: 'warning' });
          return;
        }
        const pool = current.subscribers.filter((item) => item.area === area.id && item.status !== 'suspended');
        const chosen = (pool.length ? pool : current.subscribers).slice(0, 4);
        dispatch({ type: 'SIM_START', areaId: area.id as AreaId });
        chosen.forEach((subscriber, index) => {
          timers.current.push(
            window.setTimeout(() => {
              dispatch({
                type: 'CUSTOMER_REPORT',
                subscriberId: subscriber.id,
                issue: index % 2 === 0 ? 'Internet Down' : 'Connection Unstable',
                channel: index === 2 ? 'voice' : 'whatsapp',
              });
            }, 450 + index * 700),
          );
        });
        timers.current.push(
          window.setTimeout(() => dispatch({ type: 'DECLARE_INCIDENT', areaId: area.id }), 450 + chosen.length * 700 + 500),
        );
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
