import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AREA_LABEL, CHANNEL_LABEL } from '../domain/labels';
import { areaHealth } from '../domain/network';
import { timeAgo } from '../domain/format';
import { usePageLoad } from '../hooks/usePageLoad';
import { useOps } from '../store/OpsProvider';
import { CaseBody } from '../components/overlays/GlobalOverlays';
import { Badge, EmptyState, ErrorState, Skeleton } from '../components/ui/primitives';

export function SupportPage() {
  const { phase, retry } = usePageLoad();
  const { state } = useOps();
  const [params, setParams] = useSearchParams();
  const [pane, setPane] = useState<'queue' | 'case' | 'context'>('queue');
  const selected = params.get('case') || state.cases.find((item) => item.status !== 'resolved')?.id || state.cases[0]?.id;
  const ordered = useMemo(() => [...state.cases].sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt)), [state.cases]);
  if (phase === 'error') return <ErrorState onRetry={retry} />;
  if (phase === 'loading') return <Skeleton className="h-[70vh]" />;
  const supportCase = state.cases.find((item) => item.id === selected);
  const subscriber = state.subscribers.find((item) => item.id === supportCase?.subscriberId);
  const health = supportCase ? areaHealth(supportCase.area, state.incidents) : 'operational';
  const plan = state.plans.find((item) => item.id === subscriber?.packageId);
  return (
    <div className="flex flex-col gap-3 lg:h-[calc(100dvh-8.5rem)]">
      <div className="flex gap-2 lg:hidden">
        {(['queue', 'case', 'context'] as const).map((item) => <button key={item} type="button" className={`rounded-lg px-3 py-1.5 text-sm capitalize ${pane === item ? 'bg-elevated text-ink' : 'text-muted'}`} onClick={() => setPane(item)}>{item === 'queue' ? 'Queue' : item === 'case' ? 'Case' : 'Context'}</button>)}
      </div>
      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[280px_minmax(0,1fr)_280px]">
        <section className={`surface min-h-0 overflow-y-auto ${pane === 'queue' ? '' : 'hidden lg:block'}`}>
          {ordered.map((item) => {
            const person = state.subscribers.find((sub) => sub.id === item.subscriberId);
            return (
              <button key={item.id} type="button" className={`block w-full border-b border-line px-3 py-3 text-left ${item.id === selected ? 'bg-elevated' : ''}`} onClick={() => { setParams({ case: item.id }); setPane('case'); }}>
                <span className="flex items-center justify-between gap-2"><span className="font-medium">{person?.name}</span><Badge value={item.priority} /></span>
                <span className="mt-1 block text-sm text-muted">{item.issue}</span>
                <span className="mt-1 block text-xs text-faint">{CHANNEL_LABEL[item.channel]} · {AREA_LABEL[item.area]} · {timeAgo(item.createdAt)}</span>
              </button>
            );
          })}
        </section>
        <section className={`surface min-h-0 overflow-y-auto p-4 ${pane === 'case' ? '' : 'hidden lg:block'}`}>
          {supportCase ? <CaseBody id={supportCase.id} /> : <EmptyState title="No case selected" body="Choose an issue from the queue." />}
        </section>
        <aside className={`surface min-h-0 overflow-y-auto p-4 text-sm ${pane === 'context' ? '' : 'hidden lg:block'}`}>
          {subscriber && supportCase ? (
            <div className="space-y-3">
              <h2 className="font-semibold">Customer and network</h2>
              <p>{subscriber.name}</p>
              <p className="text-muted">{subscriber.accountId}</p>
              <p>Area health: <Badge value={health} /></p>
              <p>Connection: <Badge value={subscriber.connection} /></p>
              <p className="text-muted">Package {plan?.name}. {plan?.speedMbps} Mbps.</p>
              <p className="text-muted">What is happening: {supportCase.issue}. Where: {AREA_LABEL[supportCase.area]}. Who: {subscriber.name}.</p>
            </div>
          ) : <EmptyState title="No customer context" body="Select a case to see the subscriber and their service area." />}
        </aside>
      </div>
    </div>
  );
}
