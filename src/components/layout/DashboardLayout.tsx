import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useOps } from '../../store/OpsProvider';
import { GlobalOverlays } from '../overlays/GlobalOverlays';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

export function DashboardLayout() {
  const { state, dispatch } = useOps();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setMobileOpen(false), [pathname]);
  return (
    <div className="min-h-screen bg-bg text-ink">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-brand focus:px-3 focus:py-2 focus:text-[#05210F]">Skip to content</a>
      <div className="lg:grid lg:grid-cols-[240px_minmax(0,1fr)]">
        <Sidebar />
        {mobileOpen ? (
          <div className="fixed inset-0 z-40 lg:hidden">
            <button type="button" className="absolute inset-0 bg-black/60" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />
            <div className="relative h-full w-[260px]"><Sidebar mobile onNavigate={() => setMobileOpen(false)} /></div>
          </div>
        ) : null}
        <div className="min-w-0">
          <Header onMenu={() => setMobileOpen(true)} />
          <main id="main" className="page-in min-w-0 p-4 md:p-6">
            <Outlet />
          </main>
        </div>
      </div>
      <GlobalOverlays />
      <div aria-live="polite" className="fixed bottom-4 right-4 z-[70] flex w-[min(20rem,calc(100vw-2rem))] flex-col gap-2">
        {state.toasts.map((item) => (
          <button key={item.id} type="button" className="toast-in rounded-lg border border-line bg-elevated px-3 py-3 text-left text-sm shadow-xl" onClick={() => dispatch({ type: 'DISMISS_TOAST', id: item.id })}>
            {item.message}
          </button>
        ))}
      </div>
    </div>
  );
}
