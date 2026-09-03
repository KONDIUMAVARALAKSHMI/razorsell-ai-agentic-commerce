import { NavLink, Outlet } from "react-router-dom";
import { ShoppingBag, LayoutDashboard } from "lucide-react";

export default function AppShell() {
  return (
    <div className="min-h-screen bg-ink-950 text-ink-100">
      <header className="sticky top-0 z-30 border-b border-ink-700 bg-ink-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-amber-signal font-display text-sm font-bold text-ink-950">
              R
            </div>
            <div className="flex flex-col leading-none">
              <span className="font-display text-[15px] font-semibold tracking-tight">RazorSell AI</span>
              <span className="font-mono text-[10px] uppercase tracking-widest text-ink-400">
                agentic checkout · test mode
              </span>
            </div>
          </div>
          <nav className="flex items-center gap-1 rounded-lg border border-ink-700 bg-ink-900 p-1">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive ? "bg-amber-signal text-ink-950" : "text-ink-300 hover:text-ink-100"
                }`
              }
            >
              <ShoppingBag size={15} />
              Shop
            </NavLink>
            <NavLink
              to="/merchant"
              className={({ isActive }) =>
                `flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive ? "bg-amber-signal text-ink-950" : "text-ink-300 hover:text-ink-100"
                }`
              }
            >
              <LayoutDashboard size={15} />
              Merchant
            </NavLink>
          </nav>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
