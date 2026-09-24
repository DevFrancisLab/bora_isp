import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bell, Menu, PlayCircle, Search } from 'lucide-react';
import { formatClock, timeAgo } from '../../domain/format';
import { activeIncidents } from '../../domain/network';
import { useOps } from '../../store/OpsProvider';
import type { NotifLink } from '../../types';
import { Button, IconButton, cn } from '../ui/primitives';

const META: Record<string, { title: string; description: string }> = {
  '/dashboard': { title: 'Network Overview', description: 'Monitor subscribers, service health, and customer issues in real time.' },
  '/dashboard/subscribers': { title: 'Subscribers', description: 'Manage customers, service status, and connectivity information.' },
  '/dashboard/support': { title: 'Support', description: 'Work customer issues against live network context.' },
  '/dashboard/network': { title: 'Network Operations', description: 'Watch sites, service areas, and incidents from one map.' },
  '/dashboard/messages': { title: 'Messages', description: 'Review WhatsApp, SMS, voice, and USSD communication.' },
  '/dashboard/plans': { title: 'Plans', description: 'Home and business packages offered by Kijani Networks.' },
  '/dashboard/payments': { title: 'Payments', description: 'Collection visibility for recent M-Pesa, bank, and card transactions.' },
  '/dashboard/settings': { title: 'Settings', description: 'ISP profile, alerts, channels, and the operations team.' },
};

export function Header({ onMenu }: { onMenu: () => void }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { state, dispatch, simulateReport, simulateOutage } = useOps();
  const meta = META[pathname] ?? META['/dashboard'];
  const [notesOpen, setNotesOpen] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const unread = state.notifications.filter((item) => !item.read).length;
  const incidents = activeIncidents(state.incidents);
  const critical = incidents.filter((item) => item.severity === 'critical').length;

  useEffect(() => {
    document.title = `${meta.title} · BoraISP`;
  }, [meta.title]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        dispatch({ type: 'OPEN', dialog: { type: 'search' } });
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dispatch]);

  const status = useMemo(() => {
    if (state.status !== 'ready') return { label: 'Checking network', className: 'text-muted' };
    if (critical) return { label: `${critical} outage${critical > 1 ? 's' : ''}`, className: 'text-crit' };
    if (incidents.length) return { label: 'Degraded', className: 'text-warn' };
    return { label: 'Operational', className: 'text-brand' };
  }, [critical, incidents.length, state.status]);

  function openLink(link: NotifLink) {
    setNotesOpen(false);
    if (link.kind === 'incident') {
      navigate('/dashboard/network');
      dispatch({ type: 'OPEN', dialog: { type: 'incident', id: link.id } });
    } else if (link.kind === 'case') navigate(`/dashboard/support?case=${link.id}`);
    else if (link.kind === 'subscriber') {
      navigate('/dashboard/subscribers');
      dispatch({ type: 'OPEN', dialog: { type: 'subscriber', id: link.id } });
    } else if (link.kind === 'payment') {
      navigate('/dashboard/payments');
      dispatch({ type: 'OPEN', dialog: { type: 'payment', id: link.id } });
    } else navigate(link.to);
  }

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/95 px-4 py-3 backdrop-blur md:px-6">
      <div className="flex items-start gap-3">
        <IconButton label="Open navigation" className="lg:hidden" onClick={onMenu}><Menu size={18} /></IconButton>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold md:text-xl">{meta.title}</h1>
          <p className="text-sm text-muted">{meta.description}</p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className="hidden items-center gap-2 rounded-lg border border-line bg-card px-3 py-2 text-sm text-faint md:flex" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'search' } })}>
            <Search size={14} />
            Search
            <span className="text-xs">Ctrl K</span>
          </button>
          <IconButton label="Search" className="md:hidden" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'search' } })}><Search size={16} /></IconButton>
          <div className="relative">
            <IconButton label="Demo controls" onClick={() => { setDemoOpen((open) => !open); setNotesOpen(false); setUserOpen(false); }}><PlayCircle size={16} /></IconButton>
            {demoOpen ? (
              <div className="absolute right-0 z-40 mt-2 w-72 rounded-xl border border-line bg-elevated p-2 shadow-xl">
                <button type="button" className="block w-full rounded-lg px-3 py-2 text-left hover:bg-card" onClick={() => { simulateReport(); setDemoOpen(false); }}>
                  <span className="block text-sm">Simulate Customer Report</span>
                  <span className="block text-xs text-muted">WhatsApp report, case, map marker, and alert</span>
                </button>
                <button type="button" disabled={state.simulatingOutage} className="block w-full rounded-lg px-3 py-2 text-left hover:bg-card disabled:opacity-50" onClick={() => { simulateOutage(); setDemoOpen(false); }}>
                  <span className="block text-sm">Simulate Outage</span>
                  <span className="block text-xs text-muted">Cluster reports, then open an incident</span>
                </button>
                <button type="button" className="block w-full rounded-lg px-3 py-2 text-left hover:bg-card" onClick={() => { dispatch({ type: 'FORCE_PAGE_ERROR' }); setDemoOpen(false); }}>
                  <span className="block text-sm">Simulate load error</span>
                  <span className="block text-xs text-muted">Shows the retry state on this page</span>
                </button>
              </div>
            ) : null}
          </div>
          <div className="relative">
            <IconButton label="Notifications" onClick={() => { setNotesOpen((open) => !open); setDemoOpen(false); setUserOpen(false); }}>
              <Bell size={16} />
              {unread ? <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-brand" /> : null}
            </IconButton>
            {notesOpen ? (
              <div className="absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-xl border border-line bg-elevated shadow-xl">
                <div className="flex items-center justify-between border-b border-line px-3 py-2">
                  <p className="text-sm font-medium">Notifications</p>
                  <button type="button" className="text-xs text-brand" onClick={() => dispatch({ type: 'MARK_ALL_READ' })}>Mark all as read</button>
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {state.notifications.length === 0 ? <p className="px-3 py-6 text-sm text-muted">You are up to date.</p> : null}
                  {state.notifications.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={cn('block w-full border-b border-line px-3 py-3 text-left hover:bg-card', !item.read && 'bg-card/60')}
                      onClick={() => { dispatch({ type: 'MARK_READ', id: item.id }); openLink(item.link); }}
                    >
                      <span className="flex items-center gap-2 text-sm font-medium">
                        {!item.read ? <span className="h-1.5 w-1.5 rounded-full bg-brand" /> : null}
                        {item.title}
                      </span>
                      <span className="mt-1 block text-xs text-muted">{item.description}</span>
                      <span className="mt-1 block font-mono text-[11px] text-faint">{formatClock(item.at)} · {timeAgo(item.at)}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
          <button type="button" className={`hidden items-center gap-2 rounded-full border border-line px-3 py-1.5 text-xs sm:flex ${status.className}`} onClick={() => navigate('/dashboard/network')}>
            <span className={`h-2 w-2 rounded-full ${critical ? 'bg-crit' : incidents.length ? 'bg-warn' : 'bg-brand'}`} />
            {status.label}
          </button>
          <div className="relative">
            <button type="button" className="grid h-9 w-9 place-items-center rounded-full bg-elevated text-xs font-semibold" aria-label="Account menu" onClick={() => { setUserOpen((open) => !open); setNotesOpen(false); setDemoOpen(false); }}>
              AH
            </button>
            {userOpen ? (
              <div className="absolute right-0 z-40 mt-2 w-56 rounded-xl border border-line bg-elevated p-2 shadow-xl">
                <p className="px-2 py-1 text-sm font-medium">Amina Hassan</p>
                <p className="px-2 pb-2 text-xs text-muted">NOC Operator · Kijani Networks</p>
                <Button variant="ghost" className="w-full justify-start" onClick={() => { setUserOpen(false); navigate('/dashboard/settings'); }}>Settings</Button>
                <Button variant="ghost" className="w-full justify-start" onClick={() => { setUserOpen(false); dispatch({ type: 'TOAST', message: 'This demo keeps you signed in as Amina Hassan.', tone: 'info' }); }}>Sign out</Button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}
