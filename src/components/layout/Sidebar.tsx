import { NavLink } from 'react-router-dom';
import { CreditCard, Headset, LayoutDashboard, MessageSquare, Package, RadioTower, Settings, Users, X } from 'lucide-react';
import { IconButton } from '../ui/primitives';

const GROUPS = [
  {
    label: 'Main',
    items: [
      { to: '/dashboard', label: 'Overview', icon: LayoutDashboard, end: true },
      { to: '/dashboard/subscribers', label: 'Subscribers', icon: Users },
      { to: '/dashboard/support', label: 'Support', icon: Headset },
      { to: '/dashboard/network', label: 'Network', icon: RadioTower },
      { to: '/dashboard/messages', label: 'Messages', icon: MessageSquare },
    ],
  },
  {
    label: 'Business',
    items: [
      { to: '/dashboard/plans', label: 'Plans', icon: Package },
      { to: '/dashboard/payments', label: 'Payments', icon: CreditCard },
    ],
  },
  {
    label: 'System',
    items: [{ to: '/dashboard/settings', label: 'Settings', icon: Settings }],
  },
];

export function Sidebar({ mobile = false, onNavigate }: { mobile?: boolean; onNavigate?: () => void }) {
  return (
    <aside className={mobile ? 'flex h-full w-[260px] flex-col bg-sidebar' : 'sticky top-0 hidden h-screen flex-col border-r border-line bg-sidebar lg:flex'}>
      <div className="flex items-center justify-between px-4 py-4">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand text-[#05210F]">
            <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
              <path d="M4 16c3.5-6 12.5-6 16 0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              <path d="M7 16c2-3.4 8-3.4 10 0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              <circle cx="12" cy="16.5" r="1.2" fill="currentColor" />
            </svg>
          </span>
          <span>
            <span className="block text-sm font-semibold tracking-tight">BoraISP</span>
            <span className="block text-xs text-faint">ISP Operations</span>
          </span>
        </div>
        {mobile ? <IconButton label="Close navigation" onClick={onNavigate}><X size={16} /></IconButton> : null}
      </div>
      <nav aria-label="Primary" className="flex-1 space-y-5 overflow-y-auto px-3 pb-4">
        {GROUPS.map((group) => (
          <div key={group.label}>
            <p className="px-3 pb-1 text-[11px] uppercase tracking-wider text-faint">{group.label}</p>
            <div className="space-y-1">
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={onNavigate}
                  className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
                >
                  <item.icon size={16} aria-hidden="true" />
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>
      <div className="border-t border-line px-4 py-4">
        <p className="text-sm font-medium">Kijani Networks</p>
        <p className="mt-1 flex items-center gap-2 text-xs text-muted">
          <span className="h-2 w-2 rounded-full bg-brand" aria-hidden="true" />
          Online
        </p>
      </div>
    </aside>
  );
}
