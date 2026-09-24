import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AREA_LABEL, CHANNEL_LABEL, METHOD_LABEL } from '../../domain/labels';
import { formatClock, formatKes, formatPhone, formatWhen, timeAgo } from '../../domain/format';
import { healthLabel, areaHealth, incidentForArea, siteHealth, siteOpenIssues } from '../../domain/network';
import { useOps } from '../../store/OpsProvider';
import { Badge, Button, Field, Select } from '../ui/primitives';
import { Drawer, Modal } from '../ui/overlays';

export function GlobalOverlays() {
  const { state, dispatch } = useOps();
  const navigate = useNavigate();
  const dialog = state.dialog;
  const close = () => dispatch({ type: 'CLOSE' });

  return (
    <>
      {dialog?.type === 'search' ? <SearchDialog /> : null}
      {dialog?.type === 'assign-incident' || dialog?.type === 'assign-case' ? <AssignModal /> : null}
      {dialog?.type === 'notify' ? <NotifyModal key={dialog.id} /> : null}
      {dialog?.type === 'add-subscriber' ? <SubscriberForm /> : null}
      {dialog?.type === 'create-case' ? <CaseForm /> : null}
      {dialog?.type === 'message' ? <MessageForm key={dialog.subscriberId ?? 'new'} /> : null}
      {dialog?.type === 'plan' ? <PlanForm key={dialog.id ?? 'new'} /> : null}
      {dialog?.type === 'add-team' ? <TeamForm /> : null}
      {dialog?.type === 'suspend' ? <SuspendModal /> : null}
      <Drawer open={dialog?.type === 'incident'} title={state.incidents.find((item) => dialog?.type === 'incident' && item.id === dialog.id)?.code ?? 'Incident'} description={state.incidents.find((item) => dialog?.type === 'incident' && item.id === dialog.id)?.title} onClose={close} width="max-w-lg">
        {dialog?.type === 'incident' ? <IncidentBody id={dialog.id} /> : null}
      </Drawer>
      <Drawer open={dialog?.type === 'subscriber'} title={state.subscribers.find((item) => dialog?.type === 'subscriber' && item.id === dialog.id)?.name ?? 'Subscriber'} onClose={close} width="max-w-lg">
        {dialog?.type === 'subscriber' ? <SubscriberBody id={dialog.id} /> : null}
      </Drawer>
      <Drawer open={dialog?.type === 'case'} title="Support case" onClose={close} width="max-w-xl">
        {dialog?.type === 'case' ? <CaseBody id={dialog.id} onOpen={() => { const id = dialog.id; close(); navigate(`/dashboard/support?case=${id}`); }} /> : null}
      </Drawer>
      <Drawer open={dialog?.type === 'payment'} title="Transaction" onClose={close}>
        {dialog?.type === 'payment' ? <PaymentBody id={dialog.id} /> : null}
      </Drawer>
      <Drawer open={dialog?.type === 'site'} title={state.sites.find((item) => dialog?.type === 'site' && item.id === dialog.id)?.name ?? 'Site'} onClose={close}>
        {dialog?.type === 'site' ? <SiteBody id={dialog.id} /> : null}
      </Drawer>
    </>
  );
}

function SearchDialog() {
  const { state, dispatch } = useOps();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const open = state.dialog?.type === 'search';
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const items: { key: string; group: string; title: string; meta: string; run: () => void }[] = [];
    const digits = q.replace(/\D/g, '');
    const hit = (text: string) => !q || text.toLowerCase().includes(q);
    const phoneHit = (phone: string) => digits.length >= 3 && phone.replace(/\D/g, '').includes(digits);
    const subscribers = state.subscribers.filter((item) => hit(`${item.name} ${item.accountId} ${AREA_LABEL[item.area]}`) || phoneHit(item.phone)).slice(0, 5);
    subscribers.forEach((item) => items.push({ key: item.id, group: 'Subscriber', title: item.name, meta: `${item.accountId} · ${AREA_LABEL[item.area]}`, run: () => { navigate('/dashboard/subscribers'); dispatch({ type: 'OPEN', dialog: { type: 'subscriber', id: item.id } }); } }));
    state.incidents.filter((item) => hit(`${item.code} ${item.title} ${AREA_LABEL[item.area]}`)).slice(0, 4).forEach((item) => items.push({ key: item.id, group: 'Incident', title: `${item.code} · ${item.title}`, meta: `${AREA_LABEL[item.area]} · ${item.status}`, run: () => { navigate('/dashboard/network'); dispatch({ type: 'OPEN', dialog: { type: 'incident', id: item.id } }); } }));
    state.cases.filter((item) => { const person = state.subscribers.find((sub) => sub.id === item.subscriberId); return hit(`${person?.name ?? ''} ${item.issue} ${AREA_LABEL[item.area]}`); }).slice(0, 4).forEach((item) => {
      const person = state.subscribers.find((sub) => sub.id === item.subscriberId);
      items.push({ key: item.id, group: 'Support Case', title: `${person?.name ?? 'Customer'} — ${item.issue}`, meta: AREA_LABEL[item.area], run: () => { dispatch({ type: 'CLOSE' }); navigate(`/dashboard/support?case=${item.id}`); } });
    });
    state.sites.filter((item) => hit(`${item.name} ${item.areaIds.map((id) => AREA_LABEL[id]).join(' ')}`)).slice(0, 4).forEach((item) => items.push({ key: item.id, group: 'Network Site', title: item.name, meta: item.areaIds.map((id) => AREA_LABEL[id]).join(', '), run: () => { navigate('/dashboard/network'); dispatch({ type: 'OPEN', dialog: { type: 'site', id: item.id } }); } }));
    return items;
  }, [dispatch, navigate, query, state.cases, state.incidents, state.sites, state.subscribers]);

  return (
    <Modal open={open} title="Search operations" description="Subscribers, incidents, support cases, and network sites." onClose={() => dispatch({ type: 'CLOSE' })}>
      <input data-autofocus className="input" placeholder="Try Mary, INC-104, or Kilimani POP" value={query} onChange={(event) => { setQuery(event.target.value); setActive(0); }} onKeyDown={(event) => {
        if (event.key === 'ArrowDown') { event.preventDefault(); setActive((index) => Math.min(results.length - 1, index + 1)); }
        if (event.key === 'ArrowUp') { event.preventDefault(); setActive((index) => Math.max(0, index - 1)); }
        if (event.key === 'Enter' && results[active]) results[active].run();
      }} />
      <div className="mt-3 max-h-80 overflow-y-auto">
        {results.length === 0 ? <p className="py-6 text-sm text-muted">No matching records.</p> : null}
        {results.map((item, index) => (
          <button key={item.key} type="button" className={`block w-full rounded-lg px-3 py-2 text-left ${index === active ? 'bg-card' : ''}`} onMouseEnter={() => setActive(index)} onClick={item.run}>
            <span className="text-[11px] uppercase tracking-wide text-faint">{item.group}</span>
            <span className="block text-sm">{item.title}</span>
            <span className="block text-xs text-muted">{item.meta}</span>
          </button>
        ))}
      </div>
    </Modal>
  );
}

function AssignModal() {
  const { state, dispatch } = useOps();
  const dialog = state.dialog;
  const open = dialog?.type === 'assign-incident' || dialog?.type === 'assign-case';
  if (!open || !dialog) return null;
  return (
    <Modal open title={dialog.type === 'assign-incident' ? 'Assign technician' : 'Assign support case'} description="Choose who should take the next action." onClose={() => dispatch({ type: 'CLOSE' })}>
      <div className="space-y-2">
        {(dialog.type === 'assign-incident' ? state.technicians : state.team).map((person) => {
          const busy = state.incidents.find((item) => item.technicianId === person.id && item.status !== 'resolved');
          return (
            <button key={person.id} type="button" className="flex w-full items-center justify-between rounded-lg border border-line px-3 py-3 text-left hover:bg-card" onClick={() => dispatch(dialog.type === 'assign-incident' ? { type: 'ASSIGN_INCIDENT', id: dialog.id, technicianId: person.id } : { type: 'ASSIGN_CASE', id: dialog.id, assigneeId: person.id })}>
              <span>
                <span className="block text-sm font-medium">{person.name}</span>
                <span className="block text-xs text-muted">{formatPhone(person.phone)}</span>
              </span>
              <span className="text-xs text-muted">{busy ? `On ${busy.code}` : 'Available'}</span>
            </button>
          );
        })}
      </div>
    </Modal>
  );
}

function NotifyModal() {
  const { state, dispatch } = useOps();
  const dialog = state.dialog;
  const incident = state.incidents.find((item) => dialog?.type === 'notify' && item.id === dialog.id);
  const [channel, setChannel] = useState<'whatsapp' | 'sms' | 'both'>('whatsapp');
  const [sent, setSent] = useState(false);
  if (dialog?.type !== 'notify' || !incident) return null;
  const label = channel === 'both' ? 'WhatsApp and SMS' : channel === 'whatsapp' ? 'WhatsApp' : 'SMS';
  return (
    <Modal open title="Notify customers" description={`${incident.affectedSubscribers} subscribers in ${AREA_LABEL[incident.area]}`} onClose={() => { setSent(false); dispatch({ type: 'CLOSE' }); }}>
      {sent || incident.notified ? (
        <div>
          <p className="text-sm">Notice queued for {incident.affectedSubscribers} subscribers on {incident.notified?.channel === 'both' ? 'WhatsApp and SMS' : incident.notified?.channel === 'sms' ? 'SMS' : 'WhatsApp'}.</p>
          <Button className="mt-4" variant="primary" onClick={() => { setSent(false); dispatch({ type: 'CLOSE' }); }}>Done</Button>
        </div>
      ) : (
        <form onSubmit={(event) => {
            event.preventDefault();
            const allowed = channel === 'both' ? state.settings.channels.whatsapp.connected || state.settings.channels.sms.connected : state.settings.channels[channel].connected;
            if (!allowed) { dispatch({ type: 'TOAST', message: 'Selected channel is disconnected. Reconnect it in Settings.', tone: 'warning' }); return; }
            dispatch({ type: 'NOTIFY_INCIDENT', id: incident.id, channel });
            setSent(true);
          }}>
          <fieldset className="space-y-2">
            <legend className="mb-2 text-sm text-muted">Channel</legend>
            {(['whatsapp', 'sms', 'both'] as const).map((option) => (
              <label key={option} className="flex items-center gap-2 text-sm">
                <input type="radio" name="channel" checked={channel === option} onChange={() => setChannel(option)} />
                {option === 'both' ? 'Both' : option === 'whatsapp' ? 'WhatsApp' : 'SMS'}
              </label>
            ))}
          </fieldset>
          <p className="mt-3 rounded-lg bg-bg p-3 text-sm text-muted">{state.settings.ispName}: We are investigating a service disruption in {AREA_LABEL[incident.area]}. Ref {incident.code}. Delivery via {label}.</p>
          <Button className="mt-4" variant="primary" type="submit">Send</Button>
        </form>
      )}
    </Modal>
  );
}

function SubscriberForm() {
  const { state, dispatch } = useOps();
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [area, setArea] = useState(state.areas[0]?.id ?? 'kilimani');
  const [packageId, setPackageId] = useState(state.plans[0]?.id ?? '');
  const [error, setError] = useState('');
  if (state.dialog?.type !== 'add-subscriber') return null;
  return (
    <Modal open title="Add subscriber" onClose={() => dispatch({ type: 'CLOSE' })}>
      <form className="space-y-3" onSubmit={(event) => {
        event.preventDefault();
        if (name.trim().length < 2 || phone.replace(/\D/g, '').length < 9) { setError('Enter a name and a valid phone number.'); return; }
        dispatch({ type: 'ADD_SUBSCRIBER', name, phone, area, packageId });
      }}>
        <Field label="Name"><input data-autofocus className="input" value={name} onChange={(event) => setName(event.target.value)} /></Field>
        <Field label="Phone"><input className="input" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+2547..." /></Field>
        <Field label="Area"><Select value={area} onChange={(event) => setArea(event.target.value as typeof area)}>{state.areas.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
        <Field label="Package"><Select value={packageId} onChange={(event) => setPackageId(event.target.value)}>{state.plans.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
        {error ? <p className="text-sm text-crit">{error}</p> : null}
        <Button variant="primary" type="submit">Add subscriber</Button>
      </form>
    </Modal>
  );
}

function CaseForm() {
  const { state, dispatch } = useOps();
  const dialog = state.dialog;
  const [issue, setIssue] = useState('Internet Down');
  const [channel, setChannel] = useState<'whatsapp' | 'voice' | 'sms' | 'ussd'>('whatsapp');
  if (dialog?.type !== 'create-case') return null;
  return (
    <Modal open title="Create support case" onClose={() => dispatch({ type: 'CLOSE' })}>
      <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); dispatch({ type: 'CUSTOMER_REPORT', subscriberId: dialog.subscriberId, issue, channel, reveal: true }); }}>
        <Field label="Issue"><Select value={issue} onChange={(event) => setIssue(event.target.value)}><option>Internet Down</option><option>Slow Internet</option><option>Connection Unstable</option></Select></Field>
        <Field label="Channel"><Select value={channel} onChange={(event) => setChannel(event.target.value as typeof channel)}>{Object.entries(CHANNEL_LABEL).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</Select></Field>
        <Button variant="primary" type="submit">Create case</Button>
      </form>
    </Modal>
  );
}

function MessageForm() {
  const { state, dispatch } = useOps();
  const dialog = state.dialog;
  const [subscriberId, setSubscriberId] = useState(dialog?.type === 'message' ? dialog.subscriberId ?? '' : '');
  const [channel, setChannel] = useState<'whatsapp' | 'sms' | 'voice' | 'ussd'>('whatsapp');
  const [body, setBody] = useState('');
  const [error, setError] = useState('');
  if (dialog?.type !== 'message') return null;
  return (
    <Modal open title="Send message" onClose={() => dispatch({ type: 'CLOSE' })}>
      <form className="space-y-3" onSubmit={(event) => {
        event.preventDefault();
        if (!subscriberId || body.trim().length < 2) { setError('Choose a recipient and write a message.'); return; }
        dispatch({ type: 'SEND_MESSAGE', subscriberId, channel, body: body.trim() });
      }}>
        <Field label="Recipient">
          <Select data-autofocus value={subscriberId} onChange={(event) => setSubscriberId(event.target.value)} disabled={Boolean(dialog.subscriberId)}>
            <option value="">Select subscriber</option>
            {state.subscribers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </Select>
        </Field>
        <Field label="Channel"><Select value={channel} onChange={(event) => setChannel(event.target.value as typeof channel)}>{Object.entries(CHANNEL_LABEL).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</Select></Field>
        <Field label="Message"><textarea className="input min-h-24" value={body} onChange={(event) => setBody(event.target.value)} /></Field>
        {error ? <p className="text-sm text-crit">{error}</p> : null}
        <Button variant="primary" type="submit">Send</Button>
      </form>
    </Modal>
  );
}

function PlanForm() {
  const { state, dispatch } = useOps();
  const dialog = state.dialog;
  const existing = state.plans.find((item) => dialog?.type === 'plan' && item.id === dialog.id);
  const [name, setName] = useState(existing?.name ?? '');
  const [speed, setSpeed] = useState(existing ? String(existing.speedMbps) : '20');
  const [price, setPrice] = useState(existing ? String(existing.priceKes) : '2000');
  const [segment, setSegment] = useState<'Home' | 'Business'>(existing?.segment ?? 'Home');
  const [error, setError] = useState('');
  if (dialog?.type !== 'plan') return null;
  return (
    <Modal open title={existing ? 'Edit plan' : 'Add plan'} onClose={() => dispatch({ type: 'CLOSE' })}>
      <form className="space-y-3" onSubmit={(event) => {
        event.preventDefault();
        const speedMbps = Number(speed);
        const priceKes = Number(price);
        if (!name.trim() || speedMbps <= 0 || priceKes <= 0) { setError('Enter a name, speed, and price.'); return; }
        if (existing) dispatch({ type: 'UPDATE_PLAN', id: existing.id, name, speedMbps, priceKes });
        else dispatch({ type: 'ADD_PLAN', name, speedMbps, priceKes, segment });
      }}>
        <Field label="Package"><input data-autofocus className="input" value={name} onChange={(event) => setName(event.target.value)} /></Field>
        <Field label="Speed (Mbps)"><input className="input" value={speed} onChange={(event) => setSpeed(event.target.value)} /></Field>
        <Field label="Monthly price (KSh)"><input className="input" value={price} onChange={(event) => setPrice(event.target.value)} /></Field>
        {!existing ? <Field label="Segment"><Select value={segment} onChange={(event) => setSegment(event.target.value as typeof segment)}><option>Home</option><option>Business</option></Select></Field> : null}
        {error ? <p className="text-sm text-crit">{error}</p> : null}
        <Button variant="primary" type="submit">{existing ? 'Save plan' : 'Add plan'}</Button>
      </form>
    </Modal>
  );
}

function TeamForm() {
  const { state, dispatch } = useOps();
  const [name, setName] = useState('');
  const [role, setRole] = useState<'Admin' | 'Support Agent' | 'Technician'>('Support Agent');
  const [phone, setPhone] = useState('');
  if (state.dialog?.type !== 'add-team') return null;
  return (
    <Modal open title="Add team member" onClose={() => dispatch({ type: 'CLOSE' })}>
      <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); if (name.trim() && phone.trim()) dispatch({ type: 'ADD_TEAM', name, role, phone }); }}>
        <Field label="Name"><input data-autofocus className="input" value={name} onChange={(event) => setName(event.target.value)} /></Field>
        <Field label="Role"><Select value={role} onChange={(event) => setRole(event.target.value as typeof role)}><option>Admin</option><option>Support Agent</option><option>Technician</option></Select></Field>
        <Field label="Phone"><input className="input" value={phone} onChange={(event) => setPhone(event.target.value)} /></Field>
        <Button variant="primary" type="submit">Add member</Button>
      </form>
    </Modal>
  );
}

function SuspendModal() {
  const { state, dispatch } = useOps();
  const dialog = state.dialog;
  const subscriber = state.subscribers.find((item) => dialog?.type === 'suspend' && item.id === dialog.id);
  if (dialog?.type !== 'suspend' || !subscriber) return null;
  return (
    <Modal open title="Suspend service" description={`${subscriber.name} will be marked offline until service is restored.`} onClose={() => dispatch({ type: 'CLOSE' })}>
      <div className="flex gap-2">
        <Button variant="danger" onClick={() => dispatch({ type: 'SUSPEND', id: subscriber.id })}>Suspend service</Button>
        <Button onClick={() => dispatch({ type: 'CLOSE' })}>Cancel</Button>
      </div>
    </Modal>
  );
}

export function IncidentActions({ id, mode }: { id: string; mode: 'panel' | 'drawer' }) {
  const { state, dispatch } = useOps();
  const incident = state.incidents.find((item) => item.id === id);
  if (!incident) return null;
  const resolved = incident.status === 'resolved';
  const acknowledged = incident.status === 'acknowledged' || incident.status === 'assigned' || resolved;
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      <Button size="sm" disabled={acknowledged} onClick={() => dispatch({ type: 'ACK_INCIDENT', id })}>Acknowledge</Button>
      <Button size="sm" disabled={resolved} onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'assign-incident', id } })}>Assign Technician</Button>
      <Button size="sm" disabled={resolved} onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'notify', id } })}>Notify Customers</Button>
      {mode === 'panel' ? <Button size="sm" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'incident', id } })}>View Incident</Button> : <Button size="sm" variant="primary" disabled={resolved} onClick={() => dispatch({ type: 'RESOLVE_INCIDENT', id })}>Mark Resolved</Button>}
    </div>
  );
}

function IncidentBody({ id }: { id: string }) {
  const { state } = useOps();
  const incident = state.incidents.find((item) => item.id === id);
  if (!incident) return null;
  const tech = state.technicians.find((item) => item.id === incident.technicianId);
  const site = state.sites.find((item) => item.id === incident.siteId);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2"><Badge value={incident.status} /><Badge value={incident.severity} /></div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div><dt className="text-faint">Started</dt><dd>{formatClock(incident.startedAt)}</dd></div>
        <div><dt className="text-faint">Affected subscribers</dt><dd>{incident.affectedSubscribers}</dd></div>
        <div><dt className="text-faint">Customer reports</dt><dd>{incident.reportCount}</dd></div>
        <div><dt className="text-faint">Network site</dt><dd>{site?.name}</dd></div>
        <div className="col-span-2"><dt className="text-faint">Assigned technician</dt><dd>{tech?.name ?? 'Unassigned'}</dd></div>
      </dl>
      <IncidentActions id={id} mode="drawer" />
      <h3 className="text-sm font-semibold">Incident timeline</h3>
      <ol className="space-y-3">
        {incident.timeline.map((event) => (
          <li key={event.id}><p className="font-mono text-xs text-faint">{formatClock(event.at)}</p><p className="text-sm">{event.text}</p></li>
        ))}
      </ol>
    </div>
  );
}

function SubscriberBody({ id }: { id: string }) {
  const { state, dispatch } = useOps();
  const subscriber = state.subscribers.find((item) => item.id === id);
  if (!subscriber) return null;
  const plan = state.plans.find((item) => item.id === subscriber.packageId);
  const issues = state.cases.filter((item) => item.subscriberId === id);
  const history = state.messages.filter((item) => item.subscriberId === id).slice(0, 5);
  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap gap-2"><Badge value={subscriber.status} /><Badge value={subscriber.connection} /></div>
      <dl className="grid grid-cols-2 gap-3">
        <div><dt className="text-faint">Account</dt><dd className="font-mono">{subscriber.accountId}</dd></div>
        <div><dt className="text-faint">Phone</dt><dd>{formatPhone(subscriber.phone)}</dd></div>
        <div><dt className="text-faint">Area</dt><dd>{AREA_LABEL[subscriber.area]}</dd></div>
        <div><dt className="text-faint">Package</dt><dd>{plan?.name}</dd></div>
      </dl>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'message', subscriberId: id } })}>Contact Customer</Button>
        <Button size="sm" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'create-case', subscriberId: id } })}>Create Support Case</Button>
        {subscriber.status === 'active' ? <Button size="sm" variant="danger" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'suspend', id } })}>Suspend Service</Button> : null}
        {subscriber.status === 'suspended' ? <Button size="sm" variant="primary" onClick={() => dispatch({ type: 'RESTORE', id })}>Restore Service</Button> : null}
        {subscriber.status === 'pending' ? <Button size="sm" variant="primary" onClick={() => dispatch({ type: 'ACTIVATE', id })}>Activate Service</Button> : null}
      </div>
      <section><h3 className="font-semibold">Account</h3><p className="text-muted">Payment status: {subscriber.paymentStatus}. Balance {formatKes(subscriber.balance)}.</p></section>
      <section><h3 className="font-semibold">Service</h3><p className="text-muted">{plan?.name} · {plan?.speedMbps} Mbps · Last seen {timeAgo(subscriber.lastSeen)}</p></section>
      <section>
        <h3 className="font-semibold">Recent issues</h3>
        {issues.length === 0 ? <p className="text-muted">No support cases.</p> : issues.map((item) => <button key={item.id} type="button" className="mt-2 block text-left" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'case', id: item.id } })}>{item.issue} · {item.status}</button>)}
      </section>
      <section>
        <h3 className="font-semibold">Communication history</h3>
        {history.length === 0 ? <p className="text-muted">No messages yet.</p> : history.map((item) => <p key={item.id} className="mt-2 text-muted">{CHANNEL_LABEL[item.channel]} · {item.direction} · {item.body}</p>)}
      </section>
      <section><h3 className="font-semibold">Payment status</h3><p className="text-muted">{subscriber.paymentStatus === 'overdue' ? `${formatKes(subscriber.balance)} overdue` : subscriber.paymentStatus === 'pending' ? 'A payment is still pending.' : 'Account is paid up.'}</p></section>
    </div>
  );
}

export function CaseBody({ id, onOpen }: { id: string; onOpen?: () => void }) {
  const { state, dispatch } = useOps();
  const supportCase = state.cases.find((item) => item.id === id);
  const [reply, setReply] = useState('');
  const [channel, setChannel] = useState<'whatsapp' | 'sms' | 'voice' | 'ussd'>(supportCase?.channel ?? 'whatsapp');
  const [error, setError] = useState('');
  if (!supportCase) return null;
  const subscriber = state.subscribers.find((item) => item.id === supportCase.subscriberId);
  const incident = state.incidents.find((item) => item.id === supportCase.incidentId && item.status !== 'resolved');
  const assignee = state.team.find((item) => item.id === supportCase.assigneeId);
  return (
    <div className="space-y-3">
      <div>
        <p className="font-semibold">{subscriber?.name}</p>
        <p className="text-sm text-muted">{supportCase.issue} · {AREA_LABEL[supportCase.area]} · {CHANNEL_LABEL[supportCase.channel]}</p>
        <div className="mt-2 flex flex-wrap gap-2"><Badge value={supportCase.status} /><Badge value={supportCase.priority} />{supportCase.escalated ? <span className="badge bg-warn/15 text-warn">Escalated</span> : null}</div>
      </div>
      {incident ? <button type="button" className="w-full rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-left text-sm" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'incident', id: incident.id } })}>Active incident {incident.code} in {AREA_LABEL[incident.area]} · {incident.status}</button> : null}
      {state.prompt?.areaId === supportCase.area ? (
        <div className="rounded-lg border border-warn/40 bg-warn/10 p-3 text-sm">
          <p className="font-medium">Possible outage in {AREA_LABEL[supportCase.area]}</p>
          <p className="text-muted">{state.prompt.reports} open reports are clustered in this service area.</p>
          <div className="mt-2 flex gap-2">
            <Button size="sm" variant="primary" onClick={() => dispatch({ type: 'DECLARE_INCIDENT', areaId: supportCase.area })}>Declare incident</Button>
            <Button size="sm" onClick={() => dispatch({ type: 'DISMISS_PROMPT' })}>Dismiss</Button>
          </div>
        </div>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => dispatch({ type: 'ACK_CASE', id })}>Acknowledge</Button>
        <Button size="sm" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'assign-case', id } })}>Assign</Button>
        <Button size="sm" onClick={() => dispatch({ type: 'ESCALATE_CASE', id })}>Escalate</Button>
        <Button size="sm" variant="primary" onClick={() => dispatch({ type: 'RESOLVE_CASE', id })}>Resolve</Button>
      </div>
      <div className="space-y-2 rounded-lg bg-bg p-3">
        {supportCase.messages.map((message) => (
          <div key={message.id} className={message.sender === 'system' ? 'text-xs text-info' : message.sender === 'agent' ? 'text-sm' : 'text-sm text-muted'}>
            <span className="mr-2 text-[11px] uppercase text-faint">{message.sender === 'agent' ? 'BoraISP' : message.sender}</span>
            {message.body}
          </div>
        ))}
      </div>
      <form className="space-y-2" onSubmit={(event) => { event.preventDefault(); if (reply.trim().length < 2) { setError('Write a message before sending.'); return; } setError(''); dispatch({ type: 'REPLY_CASE', id, channel, body: reply.trim() }); setReply(''); }}>
        <Select value={channel} onChange={(event) => setChannel(event.target.value as typeof channel)}>{Object.entries(CHANNEL_LABEL).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</Select>
        <textarea className="input min-h-20" placeholder="Reply to the customer" value={reply} onChange={(event) => setReply(event.target.value)} />
        {error ? <p className="text-xs text-crit">{error}</p> : null}
        <Button size="sm" variant="primary" type="submit">Send reply</Button>
      </form>
      {assignee ? <p className="text-xs text-muted">Assigned to {assignee.name}</p> : null}
      {onOpen ? <Button size="sm" onClick={onOpen}>Open in Support</Button> : null}
    </div>
  );
}

function PaymentBody({ id }: { id: string }) {
  const { state } = useOps();
  const payment = state.payments.find((item) => item.id === id);
  if (!payment) return null;
  const subscriber = state.subscribers.find((item) => item.id === payment.subscriberId);
  const plan = state.plans.find((item) => item.id === subscriber?.packageId);
  return (
    <dl className="space-y-2 text-sm">
      <div><dt className="text-faint">Customer</dt><dd>{subscriber?.name}</dd></div>
      <div><dt className="text-faint">Account</dt><dd className="font-mono">{subscriber?.accountId}</dd></div>
      <div><dt className="text-faint">Amount</dt><dd>{formatKes(payment.amount)}</dd></div>
      <div><dt className="text-faint">Method</dt><dd>{METHOD_LABEL[payment.method]}</dd></div>
      <div><dt className="text-faint">Date</dt><dd>{formatWhen(payment.at)}</dd></div>
      <div><dt className="text-faint">Status</dt><dd><Badge value={payment.status} /></dd></div>
      <div><dt className="text-faint">Reference</dt><dd className="font-mono">{payment.reference}</dd></div>
      <div><dt className="text-faint">Package</dt><dd>{plan?.name}</dd></div>
    </dl>
  );
}

function SiteBody({ id }: { id: string }) {
  const { state, dispatch } = useOps();
  const site = state.sites.find((item) => item.id === id);
  if (!site) return null;
  const health = siteHealth(site, state.incidents);
  const related = state.incidents.filter((item) => site.areaIds.includes(item.area));
  return (
    <div className="space-y-3 text-sm">
      <Badge value={health} />
      <p>Connected subscribers: {site.served}</p>
      <p>Open issues: {siteOpenIssues(site, state.cases)}</p>
      <p>Areas: {site.areaIds.map((areaId) => {
        const incident = incidentForArea(areaId, state.incidents);
        return `${AREA_LABEL[areaId]} (${healthLabel(areaHealth(areaId, state.incidents), incident)})`;
      }).join(', ')}</p>
      {related.map((incident) => (
        <button key={incident.id} type="button" className="block text-left text-brand" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'incident', id: incident.id } })}>{incident.code} · {incident.title}</button>
      ))}
    </div>
  );
}
