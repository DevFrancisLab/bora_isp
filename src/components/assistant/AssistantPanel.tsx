import { createContext, useContext, useEffect, useRef, useState, type Dispatch, type FormEvent, type ReactNode, type SetStateAction } from 'react';
import { createPortal } from 'react-dom';
import { SquarePen, X } from 'lucide-react';
import { askAssistant, askCustomerWorkflow, assistantErrorMessage, type AssistantAction } from '../../services/api';
import { useOps } from '../../store/OpsProvider';
import { IconButton } from '../ui/primitives';

interface AssistantTarget {
  subscriberId?: number;
  subscriberName?: string;
}

interface Turn {
  id: string;
  role: 'operator' | 'assistant';
  text: string;
  actions?: AssistantAction[];
  provider?: string;
  decision?: string;
  error?: boolean;
}

interface AssistantContextValue {
  openAssistant: (target?: AssistantTarget) => void;
}

const AssistantContext = createContext<AssistantContextValue | null>(null);

const PROMPTS = [
  "What's happening with customer 0712438221?",
  'Show me customers whose internet is disconnected.',
  'Does this customer need a technician?',
  'Create a support case for this customer',
];

const CUSTOMER_DEMO = 'Internet yangu imekuwa down tangu asubuhi.';

export function AssistantProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState<AssistantTarget>({});
  const [turns, setTurns] = useState<Turn[]>([]);
  return (
    <AssistantContext.Provider value={{ openAssistant: (next) => { setTarget(next ?? {}); setOpen(true); } }}>
      {children}
      <AssistantDrawer open={open} target={target} turns={turns} setTurns={setTurns} onClose={() => setOpen(false)} />
    </AssistantContext.Provider>
  );
}

export function useAssistant() {
  const context = useContext(AssistantContext);
  if (!context) throw new Error('useAssistant must be used within AssistantProvider');
  return context;
}

function AssistantDrawer({ open, target, turns, setTurns, onClose }: { open: boolean; target: AssistantTarget; turns: Turn[]; setTurns: Dispatch<SetStateAction<Turn[]>>; onClose: () => void }) {
  const { reload } = useOps();
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState(false);
  const [confirmNew, setConfirmNew] = useState(false);
  const requestRef = useRef(0);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (confirmNew) setConfirmNew(false);
      else onCloseRef.current();
    };
    document.addEventListener('keydown', onKey);
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 20);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', onKey);
      window.clearTimeout(focusTimer);
    };
  }, [open, confirmNew]);

  useEffect(() => {
    if (!open) return;
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [open, turns, pending]);

  if (!open) return null;

  function startNewChat() {
    requestRef.current += 1;
    setPending(false);
    setDraft('');
    setTurns([]);
    setConfirmNew(false);
    window.setTimeout(() => inputRef.current?.focus(), 20);
  }

  async function submit(text: string) {
    const message = text.trim();
    if (!message || pending) {
      if (!message) setTurns((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', text: 'Enter a question for the AI Operations Assistant.', error: true }]);
      return;
    }
    const history = turns
      .filter((turn) => !turn.error && turn.text.trim())
      .slice(-8)
      .map((turn) => ({ role: turn.role, content: turn.text }));
    const requestId = ++requestRef.current;
    setConfirmNew(false);
    setDraft('');
    setPending(true);
    setTurns((current) => [...current, { id: crypto.randomUUID(), role: 'operator', text: message }]);
    try {
      const result = await askAssistant({
        message,
        history,
        context: target.subscriberId ? { subscriber_id: target.subscriberId } : undefined,
      });
      if (requestRef.current !== requestId) return;
      setTurns((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', text: result.reply, actions: result.actions, provider: result.provider, decision: result.decision }]);
      if (result.actions.some((item) => (item.type === 'support_case_created' || item.type === 'incident_assignment') && item.status === 'success')) {
        await reload().catch(() => undefined);
      }
    } catch (error) {
      if (requestRef.current !== requestId) return;
      setTurns((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', text: assistantErrorMessage(error), error: true }]);
    } finally {
      if (requestRef.current === requestId) setPending(false);
    }
  }

  async function submitCustomer() {
    const message = CUSTOMER_DEMO;
    if (pending) return;
    const requestId = ++requestRef.current;
    setConfirmNew(false);
    setDraft('');
    setPending(true);
    setTurns((current) => [...current, { id: crypto.randomUUID(), role: 'operator', text: message }]);
    try {
      const result = await askCustomerWorkflow({
        message,
        phone: '0712438221',
        channel: 'whatsapp',
      });
      if (requestRef.current !== requestId) return;
      setTurns((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', text: result.reply, actions: result.actions, provider: result.provider, decision: result.decision }]);
      if (result.actions.some((item) => (item.type === 'support_case_created' || item.type === 'incident_assignment') && item.status === 'success')) {
        await reload().catch(() => undefined);
      }
    } catch (error) {
      if (requestRef.current !== requestId) return;
      setTurns((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', text: assistantErrorMessage(error), error: true }]);
    } finally {
      if (requestRef.current === requestId) setPending(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void submit(draft);
  }

  return createPortal(
    <div className="fixed inset-0 z-[1100] flex justify-end">
      <button type="button" className="absolute inset-0 bg-black/60" aria-label="Close panel" onClick={onClose} />
      <div role="dialog" aria-modal="true" aria-label="AI Operations Assistant" className="drawer-in relative z-10 flex h-full w-full max-w-lg flex-col border-l border-line bg-sidebar shadow-2xl">
        <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-4">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold">AI Operations Assistant</h2>
            <p className="mt-1 text-sm text-muted">Ask about subscribers, outages, and support cases. BASIX answers when it is configured. Groq remains the fallback.</p>
            {target.subscriberName ? <p className="mt-1 text-xs text-faint">Viewing {target.subscriberName}</p> : null}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {confirmNew ? (
              <div className="flex items-center gap-1">
                <button type="button" className="btn btn-secondary px-2.5 py-1.5 text-xs" onClick={startNewChat}>Clear chat</button>
                <button type="button" className="btn btn-ghost px-2.5 py-1.5 text-xs" onClick={() => setConfirmNew(false)}>Cancel</button>
              </div>
            ) : (
              <button type="button" className="btn btn-ghost px-2.5 py-1.5 text-xs" onClick={() => setConfirmNew(true)} disabled={turns.length === 0}>
                <SquarePen size={14} /> New chat
              </button>
            )}
            <IconButton label="Close" onClick={onClose}><X size={16} /></IconButton>
          </div>
        </header>
        <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto overscroll-contain p-4">
          {turns.length === 0 ? (
            <div className="space-y-2">
              <p className="text-sm text-muted">Internal tool for ISP operators. The customer demo uses the seeded WhatsApp line for Mary Wanjiku.</p>
              <button type="button" className="block w-full rounded-lg border border-line bg-card px-3 py-2 text-left text-sm hover:bg-elevated" onClick={() => void submitCustomer()}>
                Customer demo: {CUSTOMER_DEMO}
              </button>
              {PROMPTS.map((prompt) => (
                <button key={prompt} type="button" className="block w-full rounded-lg border border-line bg-card px-3 py-2 text-left text-sm hover:bg-elevated" onClick={() => void submit(prompt)}>
                  {prompt}
                </button>
              ))}
            </div>
          ) : turns.map((turn) => (
            <article key={turn.id} className={turn.role === 'operator' ? 'ml-8 rounded-lg bg-card px-3 py-2' : 'mr-8 rounded-lg border border-line px-3 py-2'}>
              <p className="text-[11px] uppercase text-faint">{turn.role === 'operator' ? 'ISP Operator' : 'ISPBora Assistant'}</p>
              <p className={`mt-1 whitespace-pre-wrap text-sm ${turn.error ? 'text-warn' : ''}`}>{turn.text}</p>
              {turn.decision || turn.provider ? (
                <p className="mt-1 text-[11px] uppercase text-faint">
                  {[turn.decision, turn.provider ? `provider ${turn.provider}` : ''].filter(Boolean).join(' · ')}
                </p>
              ) : null}
              {turn.actions && turn.actions.length > 0 ? (
                <div className="mt-2 border-t border-line pt-2">
                  <p className="text-[11px] uppercase text-faint">Agent activity</p>
                  <ul className="mt-1 space-y-1 text-sm">
                    {turn.actions.map((action, index) => (
                      <li key={`${action.type}-${index}`}>{action.status === 'success' ? '✓' : action.status === 'queued' ? '•' : action.status === 'unavailable' ? '⚠' : '!'} {action.label}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </article>
          ))}
          {pending ? <p className="text-sm text-muted">Checking ISP records…</p> : null}
        </div>
        <form className="border-t border-line p-4" onSubmit={onSubmit}>
          <div className="flex gap-2">
            <input ref={inputRef} data-autofocus className="input" placeholder="Ask about a subscriber, outage, or support case..." value={draft} onChange={(event) => setDraft(event.target.value)} disabled={pending} />
            <button type="submit" className="btn btn-primary" disabled={pending}>Ask</button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  );
}
