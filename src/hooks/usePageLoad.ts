import { useEffect, useRef, useState } from 'react';
import { useOps } from '../store/OpsProvider';

export function usePageLoad() {
  const { state, dispatch } = useOps();
  const [phase, setPhase] = useState<'loading' | 'ready' | 'error'>('loading');
  const booting = useRef(state.status !== 'ready');

  useEffect(() => {
    if (state.status === 'error' || state.forcePageError) {
      setPhase('error');
      return;
    }
    if (state.status !== 'ready') {
      setPhase('loading');
      return;
    }
    if (booting.current) {
      booting.current = false;
      setPhase('ready');
      return;
    }
    setPhase('loading');
    const timer = window.setTimeout(() => setPhase('ready'), 240);
    return () => window.clearTimeout(timer);
  }, [state.status, state.forcePageError, state.pageRetry]);

  return { phase, retry: () => dispatch({ type: 'CLEAR_PAGE_ERROR' }) };
}
