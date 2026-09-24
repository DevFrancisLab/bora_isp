import { useMemo, useState } from 'react';
import { AREA_LABEL } from '../domain/labels';
import { activeIncidents, areaHealth, siteHealth, siteOpenIssues, visibleReports } from '../domain/network';
import { formatClock, formatNumber } from '../domain/format';
import { usePageLoad } from '../hooks/usePageLoad';
import { useOps } from '../store/OpsProvider';
import { NetworkMap } from '../components/map/NetworkMap';
import { Badge, Button, EmptyState, ErrorState, Select, Skeleton } from '../components/ui/primitives';

export function NetworkPage() {
  const { phase, retry } = usePageLoad();
  const { state, dispatch } = useOps();
  const [filter, setFilter] = useState<'active' | 'all'>('active');
  const incidents = useMemo(() => (filter === 'active' ? activeIncidents(state.incidents) : [...state.incidents].sort((a, b) => +new Date(b.startedAt) - +new Date(a.startedAt))), [filter, state.incidents]);
  if (phase === 'error') return <ErrorState onRetry={retry} />;
  if (phase === 'loading') return <Skeleton className="h-[70vh]" />;
  const healthySites = state.sites.filter((site) => siteHealth(site, state.incidents) === 'operational').length;
  const affected = activeIncidents(state.incidents).reduce((sum, item) => sum + item.affectedSubscribers, 0);
  return (
    <div className="space-y-4">
      <section className="grid gap-3 sm:grid-cols-3">
        <article className="surface p-4"><p className="text-sm text-muted">Healthy sites</p><p className="font-mono text-2xl">{healthySites}/{state.sites.length}</p></article>
        <article className="surface p-4"><p className="text-sm text-muted">Active incidents</p><p className="font-mono text-2xl">{activeIncidents(state.incidents).length}</p></article>
        <article className="surface p-4"><p className="text-sm text-muted">Subscribers affected</p><p className="font-mono text-2xl">{formatNumber(affected)}</p></article>
      </section>
      <NetworkMap
        areas={state.areas}
        sites={state.sites}
        reports={visibleReports(state.reports, state.cases, state.incidents)}
        incidents={state.incidents}
        focusArea={state.mapFocus.areaId}
        focusNonce={state.mapFocus.nonce}
        onViewIncident={(id) => dispatch({ type: 'OPEN', dialog: { type: 'incident', id } })}
        onOpenCase={(id) => dispatch({ type: 'OPEN', dialog: { type: 'case', id } })}
        onViewSite={(id) => dispatch({ type: 'OPEN', dialog: { type: 'site', id } })}
      />
      <section className="grid gap-4 xl:grid-cols-2">
        <article className="surface overflow-hidden">
          <h2 className="px-4 py-3 text-sm font-semibold">Network sites</h2>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr><th className="th">Site</th><th className="th">Area</th><th className="th">Status</th><th className="th">Connected subscribers</th><th className="th">Open issues</th></tr></thead>
              <tbody>
                {state.sites.map((site) => (
                  <tr key={site.id} className="cursor-pointer" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'site', id: site.id } })}>
                    <td className="td">{site.name}</td>
                    <td className="td">{site.areaIds.map((id) => AREA_LABEL[id]).join(', ')}</td>
                    <td className="td"><Badge value={siteHealth(site, state.incidents)} /></td>
                    <td className="td">{formatNumber(site.served)}</td>
                    <td className="td">{siteOpenIssues(site, state.cases)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
        <article className="surface overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3">
            <h2 className="text-sm font-semibold">Incidents</h2>
            <Select value={filter} onChange={(event) => setFilter(event.target.value as typeof filter)}><option value="active">Active</option><option value="all">All</option></Select>
          </div>
          {incidents.length === 0 ? <div className="p-4"><EmptyState title="No active outages" body="All monitored service areas are currently operational." /></div> : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead><tr><th className="th">Incident</th><th className="th">Area</th><th className="th">Severity</th><th className="th">Affected</th><th className="th">Status</th><th className="th">Started</th><th className="th">Action</th></tr></thead>
                <tbody>
                  {incidents.map((incident) => (
                    <tr key={incident.id}>
                      <td className="td">{incident.code}<div className="text-xs text-muted">{incident.title}</div></td>
                      <td className="td">{AREA_LABEL[incident.area]}</td>
                      <td className="td"><Badge value={incident.severity} /></td>
                      <td className="td">{incident.affectedSubscribers}</td>
                      <td className="td"><Badge value={incident.status} /></td>
                      <td className="td">{formatClock(incident.startedAt)}</td>
                      <td className="td"><Button size="sm" onClick={() => dispatch({ type: 'OPEN', dialog: { type: 'incident', id: incident.id } })}>View</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <ul className="border-t border-line p-3 text-sm">
            {state.areas.map((area) => <li key={area.id} className="flex justify-between py-1"><span>{area.name}</span><Badge value={areaHealth(area.id, state.incidents)} /></li>)}
          </ul>
        </article>
      </section>
    </div>
  );
}
