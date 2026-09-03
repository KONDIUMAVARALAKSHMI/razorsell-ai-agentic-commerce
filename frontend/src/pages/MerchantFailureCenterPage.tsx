import { useEffect, useState } from "react";
import { AlertOctagon, RefreshCw, ShieldOff } from "lucide-react";
import { api } from "../lib/api";
import { formatTime } from "../lib/format";
import ActorBadge from "../components/ActorBadge";
import type { AuditEvent } from "../types/api";

function useFilteredEvents(eventType: string) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listAuditEvents({ event_type: eventType, limit: "100" })
      .then((res) => {
        if (!cancelled) setEvents(res);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [eventType]);

  return { events, loading };
}

function FailureList({ title, icon, eventType, tone }: { title: string; icon: React.ReactNode; eventType: string; tone: string }) {
  const { events, loading } = useFilteredEvents(eventType);

  return (
    <div className="rounded-xl border border-ink-700 bg-ink-900">
      <div className="flex items-center gap-2 border-b border-ink-700 px-4 py-3">
        <span className={tone}>{icon}</span>
        <p className="font-display text-sm font-semibold">{title}</p>
        <span className="ml-auto font-mono text-xs text-ink-500">{events.length}</span>
      </div>
      <div className="ledger-scroll max-h-64 overflow-y-auto">
        {loading ? (
          <p className="p-4 text-xs text-ink-500">Loading...</p>
        ) : events.length === 0 ? (
          <p className="p-4 text-xs text-ink-500">None recorded yet.</p>
        ) : (
          <ul className="divide-y divide-ink-800">
            {events.map((e) => (
              <li key={e.event_id} className="flex flex-col gap-1 px-4 py-2.5 font-mono text-[12px]">
                <div className="flex items-center gap-2">
                  <span className="text-ink-500">{formatTime(e.timestamp)}</span>
                  <ActorBadge actor={e.actor} />
                  {e.order_id && <span className="text-ink-600">order:{e.order_id.slice(0, 8)}</span>}
                </div>
                <p className="text-ink-300">{e.action}</p>
                {e.reason && <p className="text-rose-failure/80">{e.reason}</p>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function MerchantFailureCenterPage() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <FailureList
        title="Payment failures"
        icon={<AlertOctagon size={15} />}
        eventType="PAYMENT_FAILED"
        tone="text-rose-failure"
      />
      <FailureList
        title="Retries requested"
        icon={<RefreshCw size={15} />}
        eventType="RETRY_REQUESTED"
        tone="text-amber-signal"
      />
      <FailureList
        title="Duplicate requests blocked"
        icon={<ShieldOff size={15} />}
        eventType="DUPLICATE_REQUEST_BLOCKED"
        tone="text-violet-ai"
      />
      <FailureList
        title="Guardrail-blocked actions"
        icon={<ShieldOff size={15} />}
        eventType="GUARDRAIL_BLOCKED"
        tone="text-rose-failure"
      />
    </div>
  );
}
