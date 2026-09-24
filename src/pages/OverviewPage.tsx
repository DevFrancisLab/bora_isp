import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, LifeBuoy, Users, Wifi } from 'lucide-react';
import { attentionCount, openIssueCount, activeIncidents, areaHealth, healthLabel, incidentForArea, primaryIncident, visibleReports } from '../domain/network';
import { AREA_LABEL } from '../domain/labels';
import { formatClock, formatNumber, onlinePercent, timeAgo } from '../domain/format';
import { usePageLoad } from '../hooks/usePageLoad';
import { useOps } from '../store/OpsProvider';
import { NetworkMap } from '../components/map/NetworkMap';
import { IncidentActions } from '../components/overlays/GlobalOverlays';
import { Badge, Button, EmptyState, ErrorState, Skeleton } from '../components/ui/primitives';

export function OverviewPage() {
  const { phase, retry } = usePageLoad();
  const { state, dispatch } = useOps();
  const navigate = useNavigate();
  if (phase === 'error') return <ErrorState onRetry={retry} />;
  if (phase === 'loading') return <OverviewSkeleton />;
  const active = state.census.active;
  const online = state.census.online;
  const issues = openIssueCount(state.cases, state.hiddenOpenIssues);
  const attention = attentionCount(state.cases, state.hiddenAttention);
  const incidents = activeIncidents(state.incidents);
  const affected = incidents.reduce((sum, item) => sum + item.affectedSubscribers, 0);
  const lead = primaryIncident(state.incidents);
  const recent = [...state.cases].sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt)).slice(0, 6);
  return (
    <div className="space-y-4">
      {state.simulatingOutage ? <div className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm">Customer reports are arriving. BoraISP is clustering them into a possible outage.</div> : null}
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi icon={<Users size={16} />} label="Active Subscribers" value={formatNumber(active)} detail="+4.8% vs last month" tone="text-brand" onClick={() => navigate('/dashboard/subscribers')} />
        <Kpi icon={<Wifi size={16} />} label="Online Subscribers" value={formatNumber(online)} detail={`${onlinePercent(active, online)}% online`} tone="text-brand" onClick={() => navigate('/dashboard/subscribers')} />
        <Kpi icon={<LifeBuoy size={16} />} label="Open Issues" value={String(issues)} detail={`${attention} require attention`} tone="text-warn" onClick={() => navigate('/dashboard/support')} />
        <Kpi icon={<AlertTriangle size={16} />} label="Active Outages" value={String(incidents.length)} detail={`${affected} subscribers affected`} tone="text-crit" onClick={() => navigate('/dashboard/network')} />
      </section>
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(300px,0.85fr)]">
        <NetworkMap
          areas={state.areas}
          sites={state.sites}
          reports={visibleReports(state.reports, state.cases, state.incidents)}
          incidents={state.incidents}
          focusArea={state.mapFocus.areaId}
          focusNonce={state.mapFocus.nonce}
          onViewIncident={(id) => dispatch({ type: 'OPEN', dialog: { type: 'incident', id } })}
          onOpenCase={(id) => navigate(`/dashboard/support?case=${id}`)}
          onViewSite={(id) => dispatch({ type: 'OPEN', dialog: { type: 'site', id } })}
        />
        <div className="space-y-4">
          <article className="surface p-4">
            <h2 className="text-sm font-semibold">Active Incident</h2>
            {lead ? (
              <div className="mt-3 space-y-3">
                <div className="flex items-start gap-2">
                  <span className={`mt-1 h-2.5 w-2.5 rounded-full ${lead.severity === 'critical' ? 'bg-crit' : 'bg-warn'}`} />
                  <div>
                    <p className="font-semibold">{lead.title}</p>
                    <p className="text-sm text-muted">{lead.code} · {lead.status}</p>
                  </div>
                </div>
                <dl className="grid grid-cols-3 gap-2 text-sm">
                  <div><dt className="text-faint">Affected</dt><dd className="font-mono text-base">{lead.affectedSubscribers}</dd></div>
                  <div><dt className="text-faint">Reports</dt><dd className="font-mono text-base">{lead.reportCount}</dd></div>
                  <div><dt className="text-faint">Started</dt><dd className="font-mono text-base">{formatClock(lead.startedAt)}</dd></div>
                </dl>
                <p className="text-sm text-muted">Network site: {state.sites.find((site) => site.id === lead.siteId)?.name}</p>
                <p className="text-sm text-muted">Technician: {state.technicians.find((tech) => tech.id === lead.technicianId)?.name ?? 'Unassigned'}</p>
                <IncidentActions id={lead.id} mode="panel" />
              </div>
            ) : <EmptyState title="No active outages" body="All monitored service areas are currently operational." />}
          </article>
          <article className="surface p-4">
            <h2 className="text-sm font-semibold">Network Status</h2>
            <ul className="mt-2">
              {state.areas.map((area) => {
                const health = areaHealth(area.id, state.incidents);
                const incident = incidentForArea(area.id, state.incidents);
                return (
                  <li key={area.id}>
                    <button type="button" className="flex w-full items-center justify-between rounded-lg px-2 py-2 text-left text-sm hover:bg-elevated" onClick={() => dispatch({ type: 'FOCUS_AREA', areaId: area.id })}>
                      <span>{area.name}</span>
                      <span className={health === 'outage' ? 'text-crit' : health === 'degraded' ? 'text-warn' : 'text-brand'}>{healthLabel(health, incident)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </article>
        </div>
      </section>
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(260px,0.7fr)]">
        <article className="surface overflow-hidden">
          <h2 className="px-4 py-3 text-sm font-semibold">Recent customer issues</h2>
          <div className="hidden overflow-x-auto md:block">
            <table className="data-table">
              <caption className="sr-only">Recent customer issues</caption>
              <thead><tr><th className="th">Customer</th><th className="th">Issue</th><th className="th">Area</th><th className="th">Channel</th><th className="th">Time</th><th className="th">Status</th><th className="th">Action</th></tr></thead>
              <tbody>
                {recent.map((item) => {
                  const person = state.subscribers.find((sub) => sub.id === item.subscriberId);
                  return (
                    <tr key={item.id}>
                      <td className="td">{person?.name}</td>
                      <td className="td">{item.issue}</td>
                      <td className="td">{AREA_LABEL[item.area]}</td>
                      <td className="td"><Badge value={item.channel} /></td>
                      <td className="td">{timeAgo(item.createdAt)}</td>
                      <td className="td"><Badge value={item.status} /></td>
                      <td className="td"><Button size="sm" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'case', id: item.id } })}>View</Button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="space-y-2 p-3 md:hidden">
            {recent.map((item) => {
              const person = state.subscribers.find((sub) => sub.id === item.subscriberId);
              return <button key={item.id} type="button" className="w-full rounded-lg border border-line p-3 text-left" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'case', id: item.id } })}><span className="block font-medium">{person?.name}</span><span className="text-sm text-muted">{item.issue} · {AREA_LABEL[item.area]} · {timeAgo(item.createdAt)}</span></button>;
            })}
          </div>
        </article>
        <article className="surface p-4">
          <h2 className="text-sm font-semibold">Activity</h2>
          <ol className="mt-3 space-y-3">
            {state.activities.slice(0, 8).map((item, index) => (
              <li key={item.id} className="border-l border-line pl-3">
                <p className={`font-mono text-xs ${index === 0 ? 'text-brand' : 'text-faint'}`}>{formatClock(item.at)}</p>
                <p className="text-sm">{item.text}</p>
              </li>
            ))}
          </ol>
        </article>
      </section>
    </div>
  );
}

function Kpi({ icon, label, value, detail, tone, onClick }: { icon: ReactNode; label: string; value: string; detail: string; tone: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="surface p-4 text-left transition-colors hover:border-brand/40 hover:bg-elevated">
      <span className="flex items-center justify-between text-sm text-muted">{label}<span className={tone}>{icon}</span></span>
      <span className="mt-3 block font-mono text-3xl">{value}</span>
      <span className={`mt-2 block text-sm ${tone}`}>{detail}</span>
    </button>
  );
}

function OverviewSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-28" />)}</div>
      <Skeleton className="h-[420px]" />
      <Skeleton className="h-48" />
    </div>
  );
}
