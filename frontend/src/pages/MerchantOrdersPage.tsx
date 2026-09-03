import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatDateTime, formatInr } from "../lib/format";
import StatusBadge from "../components/StatusBadge";
import type { OrderSummary } from "../types/api";

export default function MerchantOrdersPage() {
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const res = await api.listOrders(100);
      setOrders(res);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (loading) return <p className="text-sm text-ink-400">Loading orders...</p>;

  return (
    <div className="rounded-xl border border-ink-700 bg-ink-900">
      <div className="flex items-center justify-between border-b border-ink-700 px-4 py-3">
        <p className="font-display text-sm font-semibold">Orders ({orders.length})</p>
        <button onClick={load} className="text-xs text-amber-signal hover:underline">
          Refresh
        </button>
      </div>
      {orders.length === 0 ? (
        <p className="p-6 text-center text-sm text-ink-400">No orders yet - complete a checkout to see it here.</p>
      ) : (
        <ul className="divide-y divide-ink-700">
          {orders.map((order) => {
            const id = (order.id || "") as string;
            const isOpen = expanded === id;
            return (
              <li key={id}>
                <button
                  onClick={() => setExpanded(isOpen ? null : id)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-ink-800"
                >
                  <div className="flex flex-col gap-0.5">
                    <span className="font-mono text-xs text-ink-400">{id.slice(0, 8)}</span>
                    <span className="text-xs text-ink-500">{order.created_at && formatDateTime(order.created_at)}</span>
                  </div>
                  <span className="font-mono text-sm text-ink-100">{formatInr(order.total_amount)}</span>
                  <StatusBadge status={order.status} />
                </button>
                {isOpen && (
                  <div className="border-t border-ink-700 bg-ink-800 px-4 py-3">
                    <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-ink-500">Items</p>
                    <ul className="mb-3 flex flex-col gap-1">
                      {order.items?.map((item, i) => (
                        <li key={i} className="flex justify-between text-xs text-ink-300">
                          <span>
                            {item.product_name} x{item.quantity}
                          </span>
                          <span className="font-mono">{formatInr(item.line_total)}</span>
                        </li>
                      ))}
                    </ul>
                    {order.payment_attempts && order.payment_attempts.length > 0 && (
                      <>
                        <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-ink-500">
                          Payment attempts
                        </p>
                        <ul className="flex flex-col gap-1">
                          {order.payment_attempts.map((a) => (
                            <li key={a.attempt_number} className="flex items-center justify-between text-xs">
                              <span className="font-mono text-ink-400">
                                #{a.attempt_number} via {a.provider}
                              </span>
                              <StatusBadge status={a.status} />
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
