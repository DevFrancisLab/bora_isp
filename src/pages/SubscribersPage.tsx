import { useMemo, useState } from 'react';
import { AREA_LABEL } from '../domain/labels';
import { formatPhone, timeAgo } from '../domain/format';
import { usePageLoad } from '../hooks/usePageLoad';
import { useOps } from '../store/OpsProvider';
import type { AreaId, ConnectionState, SubscriberStatus } from '../types';
import { Badge, Button, EmptyState, ErrorState, Select, Skeleton } from '../components/ui/primitives';

export function SubscribersPage() {
  const { phase, retry } = usePageLoad();
  const { state, dispatch } = useOps();
  const [query, setQuery] = useState('');
  const [area, setArea] = useState<'all' | AreaId>('all');
  const [status, setStatus] = useState<'all' | SubscriberStatus>('all');
  const [connection, setConnection] = useState<'all' | ConnectionState>('all');
  const [packageId, setPackageId] = useState('all');
  const rows = useMemo(() => state.subscribers.filter((item) => {
    const q = query.trim().toLowerCase();
    const digits = query.replace(/\D/g, '');
    const matches = !q || item.name.toLowerCase().includes(q) || item.accountId.toLowerCase().includes(q) || (digits.length >= 3 && item.phone.replace(/\D/g, '').includes(digits));
    return matches && (area === 'all' || item.area === area) && (status === 'all' || item.status === status) && (connection === 'all' || item.connection === connection) && (packageId === 'all' || item.packageId === packageId);
  }), [area, connection, packageId, query, state.subscribers, status]);
  if (phase === 'error') return <ErrorState onRetry={retry} />;
  if (phase === 'loading') return <Skeleton className="h-96" />;
  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 lg:flex-row">
        <input className="input lg:max-w-xs" placeholder="Search name, phone, or account" value={query} onChange={(event) => setQuery(event.target.value)} />
        <Select value={area} onChange={(event) => setArea(event.target.value as typeof area)}><option value="all">All areas</option>{state.areas.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select>
        <Select value={status} onChange={(event) => setStatus(event.target.value as typeof status)}><option value="all">All statuses</option><option value="active">Active</option><option value="suspended">Suspended</option><option value="pending">Pending</option></Select>
        <Select value={packageId} onChange={(event) => setPackageId(event.target.value)}><option value="all">All packages</option>{state.plans.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select>
        <Select value={connection} onChange={(event) => setConnection(event.target.value as typeof connection)}><option value="all">All connections</option><option value="online">Online</option><option value="offline">Offline</option><option value="unstable">Unstable</option></Select>
        <Button variant="primary" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'add-subscriber' } })}>Add Subscriber</Button>
      </div>
      {rows.length === 0 ? <EmptyState title="No subscribers match" body="Adjust the search or filters to see the directory." /> : (
        <>
          <div className="surface hidden overflow-x-auto md:block">
            <table className="data-table">
              <caption className="sr-only">Subscribers</caption>
              <thead><tr><th className="th">Customer</th><th className="th">Phone</th><th className="th">Area</th><th className="th">Package</th><th className="th">Status</th><th className="th">Connection</th><th className="th">Last Seen</th><th className="th">Actions</th></tr></thead>
              <tbody>
                {rows.map((item) => (
                  <tr key={item.id}>
                    <td className="td">{item.name}<div className="font-mono text-xs text-faint">{item.accountId}</div></td>
                    <td className="td">{formatPhone(item.phone)}</td>
                    <td className="td">{AREA_LABEL[item.area]}</td>
                    <td className="td">{state.plans.find((plan) => plan.id === item.packageId)?.name}</td>
                    <td className="td"><Badge value={item.status} /></td>
                    <td className="td"><Badge value={item.connection} /></td>
                    <td className="td">{timeAgo(item.lastSeen)}</td>
                    <td className="td"><Button size="sm" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'subscriber', id: item.id } })}>View</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="space-y-2 md:hidden">
            {rows.map((item) => <button key={item.id} type="button" className="surface w-full p-3 text-left" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'subscriber', id: item.id } })}><span className="font-medium">{item.name}</span><span className="block text-sm text-muted">{AREA_LABEL[item.area]} · {item.connection}</span></button>)}
          </div>
        </>
      )}
    </div>
  );
}
