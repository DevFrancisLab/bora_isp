import { useEffect, useMemo, useRef, useState } from 'react';
import { CHANNEL_LABEL, METHOD_LABEL } from '../domain/labels';
import { formatKes, formatWhen, timeAgo } from '../domain/format';
import { usePageLoad } from '../hooks/usePageLoad';
import { useOps } from '../store/OpsProvider';
import type { Channel } from '../types';
import { ApiError, createTechnician, deleteTechnician } from '../services/api';
import { Badge, Button, EmptyState, ErrorState, Skeleton } from '../components/ui/primitives';

export function MessagesPage() {
  const { phase, retry } = usePageLoad();
  const { state, dispatch } = useOps();
  const [tab, setTab] = useState<'all' | Channel>('all');
  const [query, setQuery] = useState('');
  const rows = useMemo(() => state.messages.filter((item) => (tab === 'all' || item.channel === tab) && (`${item.recipientLabel} ${item.body}`.toLowerCase().includes(query.trim().toLowerCase()))), [query, state.messages, tab]);
  if (phase === 'error') return <ErrorState onRetry={retry} />;
  if (phase === 'loading') return <Skeleton className="h-96" />;
  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        <div className="flex flex-wrap gap-2">
          {(['all', 'whatsapp', 'sms', 'voice', 'ussd'] as const).map((item) => <button key={item} type="button" className={`rounded-full px-3 py-1.5 text-sm ${tab === item ? 'bg-brand text-[#05210F]' : 'bg-elevated text-muted'}`} onClick={() => setTab(item)}>{item === 'all' ? 'All' : CHANNEL_LABEL[item]}</button>)}
        </div>
        <input className="input md:max-w-xs" placeholder="Filter messages" value={query} onChange={(event) => setQuery(event.target.value)} />
        <Button variant="primary" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'message' } })}>Send Message</Button>
      </div>
      {rows.length === 0 ? <EmptyState title={state.messages.length === 0 ? 'No messages.' : 'No messages'} body={state.messages.length === 0 ? 'Outbound and inbound records will appear here.' : 'Nothing in this channel matches the current filter.'} /> : (
        <div className="surface overflow-x-auto">
          <table className="data-table">
            <thead><tr><th className="th">Customer</th><th className="th">Channel</th><th className="th">Message</th><th className="th">Direction</th><th className="th">Status</th><th className="th">Time</th></tr></thead>
            <tbody>
              {rows.map((item) => (
                <tr key={item.id}>
                  <td className="td">{item.recipientLabel}</td>
                  <td className="td"><Badge value={item.channel} /></td>
                  <td className="td max-w-md"><span className="line-clamp-2">{item.body}</span></td>
                  <td className="td capitalize">{item.direction}</td>
                  <td className="td"><Badge value={item.status} /></td>
                  <td className="td whitespace-nowrap">{timeAgo(item.at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function PlansPage() {
  const { phase, retry } = usePageLoad();
  const { state, dispatch } = useOps();
  if (phase === 'error') return <ErrorState onRetry={retry} />;
  if (phase === 'loading') return <Skeleton className="h-80" />;
  return (
    <div className="space-y-4">
      <Button variant="primary" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'plan' } })}>Add Plan</Button>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {state.plans.map((plan) => {
          const count = state.subscribers.filter((item) => item.packageId === plan.id).length;
          return (
            <article key={plan.id} className="surface p-4">
              <div className="flex items-start justify-between gap-2">
                <h2 className="font-semibold">{plan.name}</h2>
                <Badge value={plan.active ? 'active' : 'inactive'} />
              </div>
              <p className="mt-2 font-mono text-xl">{formatKes(plan.priceKes)}<span className="text-sm text-muted">/month</span></p>
              <p className="mt-1 text-sm text-muted">{plan.speedMbps} Mbps · {plan.segment}</p>
              <p className="mt-1 text-sm text-muted">{count} subscribers in directory</p>
              <div className="mt-4 flex gap-2">
                <Button size="sm" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'plan', id: plan.id } })}>Edit</Button>
                <Button size="sm" onClick={() => dispatch({ type: 'TOGGLE_PLAN', id: plan.id })}>{plan.active ? 'Deactivate' : 'Activate'}</Button>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}

export function PaymentsPage() {
  const { phase, retry } = usePageLoad();
  const { state, dispatch } = useOps();
  if (phase === 'error') return <ErrorState onRetry={retry} />;
  if (phase === 'loading') return <Skeleton className="h-96" />;
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const collected = state.payments.filter((item) => item.status === 'paid' && new Date(item.at) >= start).reduce((sum, item) => sum + item.amount, 0);
  const pending = state.payments.filter((item) => item.status === 'pending').reduce((sum, item) => sum + item.amount, 0);
  const overdue = state.subscribers.filter((item) => item.paymentStatus === 'overdue').length;
  return (
    <div className="space-y-4">
      <section className="grid gap-3 sm:grid-cols-3">
        <article className="surface p-4"><p className="text-sm text-muted">Collected today</p><p className="font-mono text-2xl">{formatKes(collected)}</p></article>
        <article className="surface p-4"><p className="text-sm text-muted">Pending payments</p><p className="font-mono text-2xl">{formatKes(pending)}</p></article>
        <article className="surface p-4"><p className="text-sm text-muted">Overdue accounts</p><p className="font-mono text-2xl">{overdue}</p></article>
      </section>
      <div className="surface overflow-x-auto">
        <table className="data-table">
          <thead><tr><th className="th">Customer</th><th className="th">Account</th><th className="th">Amount</th><th className="th">Method</th><th className="th">Date</th><th className="th">Status</th></tr></thead>
          <tbody>
            {state.payments.map((item) => {
              const person = state.subscribers.find((sub) => sub.id === item.subscriberId);
              return (
                <tr key={item.id} className="cursor-pointer" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'payment', id: item.id } })}>
                  <td className="td">{person?.name}</td>
                  <td className="td font-mono">{person?.accountId}</td>
                  <td className="td">{formatKes(item.amount)}</td>
                  <td className="td">{METHOD_LABEL[item.method]}</td>
                  <td className="td whitespace-nowrap">{formatWhen(item.at)}</td>
                  <td className="td"><Badge value={item.status} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function technicianError(error: unknown, fallback: string) {
  if (!(error instanceof ApiError)) return fallback;
  const match = error.message.match(/"detail"\s*:\s*"([^"]+)"/);
  if (match) return match[1];
  if (error.message.includes('phone_number')) return 'Enter a valid Kenyan phone number that is not already in use.';
  if (error.message.includes('service_area')) return 'Choose a service area.';
  if (error.message.includes('name')) return "Enter the technician's name.";
  return fallback;
}

export function SettingsPage() {
  const { phase, retry } = usePageLoad();
  const { state, dispatch, reload } = useOps();
  const [technicianForm, setTechnicianForm] = useState({ name: '', phone: '', email: '', serviceArea: '' });
  const [savingTechnician, setSavingTechnician] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [profile, setProfile] = useState(state.settings);
  const sawProfile = useRef(state.settings.ispName.length > 0);
  useEffect(() => {
    if (state.status === 'ready' && !sawProfile.current && state.settings.ispName) {
      sawProfile.current = true;
      setProfile(state.settings);
    }
  }, [state.settings, state.status]);
  if (phase === 'error') return <ErrorState onRetry={retry} />;
  if (phase === 'loading') return <Skeleton className="h-96" />;
  const set = (key: 'ispName' | 'phone' | 'email' | 'location', value: string) => setProfile((current) => ({ ...current, [key]: value }));
  const areas = state.areas.filter((area) => area.remoteId);

  async function addTechnician() {
    const area = areas.find((item) => String(item.remoteId) === technicianForm.serviceArea);
    if (!technicianForm.name.trim() || !technicianForm.phone.trim() || !area?.remoteId) {
      dispatch({ type: 'TOAST', message: 'Enter a name, phone number, and service area.', tone: 'warning' });
      return;
    }
    setSavingTechnician(true);
    try {
      await createTechnician({
        name: technicianForm.name.trim(),
        phone_number: technicianForm.phone.trim(),
        email: technicianForm.email.trim(),
        service_area: area.remoteId,
      });
      setTechnicianForm({ name: '', phone: '', email: '', serviceArea: '' });
      await reload();
      dispatch({ type: 'TOAST', message: 'Technician added', tone: 'success' });
    } catch (error) {
      dispatch({ type: 'TOAST', message: technicianError(error, 'The technician could not be added.'), tone: 'warning' });
    } finally {
      setSavingTechnician(false);
    }
  }

  async function removeTechnician(id: string) {
    setSavingTechnician(true);
    try {
      await deleteTechnician(Number(id));
      setPendingDelete(null);
      await reload();
      dispatch({ type: 'TOAST', message: 'Technician removed', tone: 'success' });
    } catch (error) {
      dispatch({ type: 'TOAST', message: technicianError(error, 'The technician could not be removed.'), tone: 'warning' });
    } finally {
      setSavingTechnician(false);
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <section className="surface space-y-3 p-4">
        <h2 className="font-semibold">ISP Profile</h2>
        <label className="block text-sm text-muted">ISP name<input className="input mt-1" value={profile.ispName} onChange={(event) => set('ispName', event.target.value)} /></label>
        <label className="block text-sm text-muted">Phone<input className="input mt-1" value={profile.phone} onChange={(event) => set('phone', event.target.value)} /></label>
        <label className="block text-sm text-muted">Email<input className="input mt-1" value={profile.email} onChange={(event) => set('email', event.target.value)} /></label>
        <label className="block text-sm text-muted">Location<input className="input mt-1" value={profile.location} onChange={(event) => set('location', event.target.value)} /></label>
        <Button variant="primary" onClick={() => {
          if (!profile.email.includes('@')) { dispatch({ type: 'TOAST', message: 'Enter a valid email address.', tone: 'warning' }); return; }
          dispatch({ type: 'SAVE_PROFILE', ispName: profile.ispName, phone: profile.phone, email: profile.email, location: profile.location });
        }}>Save profile</Button>
      </section>
      <section className="surface space-y-3 p-4">
        <h2 className="font-semibold">Notifications</h2>
        {([
          ['outage', 'Outage notifications'],
          ['support', 'New support issue alerts'],
          ['technician', 'Technician updates'],
          ['payment', 'Payment alerts'],
        ] as const).map(([key, label]) => (
          <div key={key} className="flex items-center justify-between gap-3 text-sm">
            <span>{label}</span>
            <button type="button" role="switch" aria-checked={state.settings.notifications[key]} className={`h-6 w-11 rounded-full ${state.settings.notifications[key] ? 'bg-brand' : 'bg-line'}`} onClick={() => dispatch({ type: 'TOGGLE_SETTING', key })}>
              <span className={`block h-5 w-5 rounded-full bg-white transition ${state.settings.notifications[key] ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </button>
          </div>
        ))}
      </section>
      <section className="surface space-y-3 p-4">
        <h2 className="font-semibold">Communication channels</h2>
        {(Object.keys(state.settings.channels) as Channel[]).map((channel) => (
          <div key={channel} className="flex items-center justify-between text-sm">
            <span>{CHANNEL_LABEL[channel]} · {state.settings.channels[channel].connected ? 'Connected' : 'Disconnected'}</span>
            <Button size="sm" onClick={() => dispatch({ type: 'TOGGLE_CHANNEL', channel })}>{state.settings.channels[channel].connected ? 'Disconnect' : 'Connect'}</Button>
          </div>
        ))}
      </section>
      <section className="surface space-y-3 p-4 xl:col-span-2">
        <div>
          <h2 className="font-semibold">Technicians</h2>
          <p className="mt-1 text-sm text-muted">These people come from the operations database and can be assigned to incidents.</p>
        </div>
        <div className="grid gap-2 md:grid-cols-4">
          <input className="input" placeholder="Name" value={technicianForm.name} onChange={(event) => setTechnicianForm((current) => ({ ...current, name: event.target.value }))} />
          <input className="input" placeholder="Phone" value={technicianForm.phone} onChange={(event) => setTechnicianForm((current) => ({ ...current, phone: event.target.value }))} />
          <input className="input" placeholder="Email (optional)" value={technicianForm.email} onChange={(event) => setTechnicianForm((current) => ({ ...current, email: event.target.value }))} />
          <select className="input" value={technicianForm.serviceArea} onChange={(event) => setTechnicianForm((current) => ({ ...current, serviceArea: event.target.value }))}>
            <option value="">Service area</option>
            {areas.map((area) => <option key={area.remoteId} value={String(area.remoteId)}>{area.name}</option>)}
          </select>
        </div>
        <Button variant="primary" size="sm" disabled={savingTechnician} onClick={() => void addTechnician()}>Add technician</Button>
        {state.technicians.length === 0 ? <p className="text-sm text-muted">No technicians are listed yet.</p> : state.technicians.map((technician) => (
          <div key={technician.id} className="flex items-center justify-between gap-3 border-t border-line pt-3 text-sm">
            <span>
              {technician.name}
              <span className="block text-xs text-faint">{technician.phone}{technician.serviceAreaName ? ` · ${technician.serviceAreaName}` : ''}{technician.status ? ` · ${technician.status.toLowerCase()}` : ''}</span>
            </span>
            {pendingDelete === technician.id ? (
              <span className="flex gap-2">
                <Button size="sm" variant="danger" disabled={savingTechnician} onClick={() => void removeTechnician(technician.id)}>Delete</Button>
                <Button size="sm" disabled={savingTechnician} onClick={() => setPendingDelete(null)}>Cancel</Button>
              </span>
            ) : (
              <Button size="sm" disabled={savingTechnician} onClick={() => setPendingDelete(technician.id)}>Remove</Button>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}
