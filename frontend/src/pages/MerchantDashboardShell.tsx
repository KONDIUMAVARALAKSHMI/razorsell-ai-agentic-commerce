import { NavLink, Navigate, Outlet } from "react-router-dom";
import { getMerchantToken } from "./MerchantLoginPage";

const TABS = [
  { to: "/merchant/overview", label: "Overview" },
  { to: "/merchant/orders", label: "Orders" },
  { to: "/merchant/audit", label: "Audit trail" },
  { to: "/merchant/failures", label: "Failure center" },
];

export default function MerchantDashboardShell() {
  const token = getMerchantToken();
  if (!token) {
    return <Navigate to="/merchant" replace />;
  }

  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-6">
      <div className="mb-5 flex flex-wrap items-center gap-1 rounded-lg border border-ink-700 bg-ink-900 p-1">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              `rounded-md px-3.5 py-1.5 text-sm font-medium transition-colors ${
                isActive ? "bg-amber-signal text-ink-950" : "text-ink-300 hover:text-ink-100"
              }`
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </div>
      <Outlet />
    </div>
  );
}
