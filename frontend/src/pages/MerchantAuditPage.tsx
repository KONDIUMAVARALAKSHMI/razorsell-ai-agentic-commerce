import { useEffect, useState } from "react";
import { Filter } from "lucide-react";
import { api } from "../lib/api";
import { formatTime } from "../lib/format";
import ActorBadge from "../components/ActorBadge";
import StatusBadge from "../components/StatusBadge";
import type { AuditEvent } from "../types/api";

const EVENT_TYPES = [
  "USER_MESSAGE", "AI_DECISION", "PRODUCT_SEARCH", "PRODUCT_RECOMMENDATION", "UPSELL_RECOMMENDATION",
  "UPSELL_ACCEPTED", "UPSELL_REJECTED", "CART_UPDATED", "CHECKOUT_STARTED", "USER_PAYMENT_CONFIRMATION",
  "RAZORPAY_ORDER_CREATED", "PAYMENT_ATTEMPTED", "PAYMENT_SUCCESS", "PAYMENT_FAILED", "RETRY_REQUESTED",
  "RETRY_BLOCKED", "GUARDRAIL_BLOCKED", "INVENTORY_BLOCKED", "DUPLICATE_REQUEST_BLOCKED",
];

export default function MerchantAuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState("");
  const [filterActor, setFilterActor] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  async function load() {
    setLoading(true);
    try {
      const res = await api.listAuditEvents({
        event_type: filterType || undefined,
        actor: filterActor || undefined,
        status: filterStatus || undefined,
        limit: "300",
      });
      setEvents(res);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterType, filterActor, filterStatus]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-ink-700 bg-ink-900 p-3">
        <Filter size={14} className="text-ink-500" />
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="rounded-md border border-ink-600 bg-ink-800 px-2 py-1.5 text-xs text-ink-200"
        >
          <option value="">All event types</option>
          {EVENT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={filterActor}
          onChange={(e) => setFilterActor(e.target.value)}
          className="rounded-md border border-ink-600 bg-ink-800 px-2 py-1.5 text-xs text-ink-200"
        >
          <option value="">All actors</option>
          <option value="USER">User</option>
          <option value="AI">AI</option>
          <option value="SYSTEM">System</option>
          <option value="RAZORPAY">Razorpay</option>
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="rounded-md border border-ink-600 bg-ink-800 px-2 py-1.5 text-xs text-ink-200"
        >
          <option value="">All statuses</option>
          <option value="OK">OK</option>
          <option value="BLOCKED">Blocked</option>
          <option value="ERROR">Error</option>
        </select>
        <button onClick={load} className="ml-auto text-xs text-amber-signal hover:underline">
          Refresh
        </button>
      </div>

      <div className="ledger-scroll max-h-[70vh] overflow-y-auto rounded-xl border border-ink-700 bg-ink-950">
        {loading ? (
          <p className="p-6 text-center text-sm text-ink-400">Loading ledger...</p>
        ) : events.length === 0 ? (
          <p className="p-6 text-center text-sm text-ink-400">No audit events match these filters yet.</p>
        ) : (
          <div className="divide-y divide-ink-800 font-mono text-[12.5px]">
            {events.map((e) => (
              <div key={e.event_id} className="flex flex-col gap-1 px-4 py-2.5 hover:bg-ink-900">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-ink-500">{formatTime(e.timestamp)}</span>
                  <ActorBadge actor={e.actor} />
                  <span className="text-ink-300">{e.event_type}</span>
                  <StatusBadge status={e.status} />
                  {e.order_id && <span className="text-ink-600">order:{e.order_id.slice(0, 8)}</span>}
                </div>
                <p className="pl-1 text-ink-400">{e.action}</p>
                {e.reason && <p className="pl-1 text-rose-failure/80">{e.reason}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
