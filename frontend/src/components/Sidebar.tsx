import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Plug,
  IdCard,
  ShieldQuestion,
  ScrollText,
  Wallet,
  RefreshCw,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/connectors", label: "Connectors", icon: Plug },
  { to: "/registry", label: "Golden Registry", icon: IdCard },
  { to: "/doubt-registry", label: "Doubt Registry", icon: ShieldQuestion },
  { to: "/consent", label: "Consent", icon: ScrollText },
  { to: "/delivery", label: "Delivery Rules", icon: Wallet },
  { to: "/openg2p-sync", label: "OpenG2P Sync", icon: RefreshCw },
];

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col bg-ink-900 text-zinc-300">
      <div className="flex items-center gap-2.5 px-5 py-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-400 text-base font-bold text-ink-900">
          SR
        </div>
        <div>
          <p className="text-sm font-semibold text-white">Social Registry</p>
          <p className="text-xs text-zinc-500">Config Console</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                isActive
                  ? "bg-ink-800 text-accent-400"
                  : "text-zinc-400 hover:bg-ink-800 hover:text-zinc-100"
              }`
            }
          >
            <Icon size={18} strokeWidth={2} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-ink-700 px-5 py-4">
        <p className="text-xs text-zinc-500">Single-tenant deployment</p>
        <p className="text-xs font-medium text-zinc-300">Delhi — Pilot</p>
      </div>
    </aside>
  );
}
