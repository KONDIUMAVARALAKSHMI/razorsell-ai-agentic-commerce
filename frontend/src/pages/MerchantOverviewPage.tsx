import { useEffect, useState } from "react";
import { BarChart3, IndianRupee, ShieldAlert, TrendingUp } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../lib/api";
import { formatInr } from "../lib/format";
import MetricCard from "../components/MetricCard";
import type { AnalyticsOverview } from "../types/api";

export default function MerchantOverviewPage() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const res = await api.analyticsOverview();
      setData(res);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 8000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return <p className="text-sm text-ink-400">Loading analytics...</p>;
  }
  if (!data) {
    return <p className="text-sm text-rose-failure">Could not load analytics.</p>;
  }

  const chartData = [
    { name: "Orders", value: data.revenue.total_orders },
    { name: "Paid", value: data.revenue.successful_payments },
    { name: "Failures", value: data.reliability.payment_failures },
    { name: "Recoveries", value: data.reliability.successful_payments },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="mb-3 font-mono text-[11px] uppercase tracking-widest text-ink-500">Revenue</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCard label="Orders" value={String(data.revenue.total_orders)} icon={<BarChart3 size={13} />} />
          <MetricCard
            label="Paid orders"
            value={String(data.revenue.successful_payments)}
            icon={<TrendingUp size={13} />}
            accent="mint"
          />
          <MetricCard
            label="Conversion"
            value={`${data.revenue.conversion_rate_percent}%`}
            icon={<TrendingUp size={13} />}
          />
          <MetricCard
            label="Revenue"
            value={formatInr(data.revenue.total_revenue)}
            icon={<IndianRupee size={13} />}
            accent="amber"
          />
          <MetricCard label="Avg order value" value={formatInr(data.revenue.average_order_value)} />
          <MetricCard
            label="Upsell revenue"
            value={formatInr(data.revenue.incremental_upsell_revenue)}
            accent="violet"
          />
        </div>
      </div>

      <div>
        <p className="mb-3 font-mono text-[11px] uppercase tracking-widest text-ink-500">Agent</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricCard label="Conversations" value={String(data.agent.conversations)} />
          <MetricCard label="Product searches" value={String(data.agent.product_searches)} />
          <MetricCard label="Recommendations shown" value={String(data.agent.recommendations_shown)} />
          <MetricCard
            label="Blocked unsafe actions"
            value={String(data.agent.blocked_unsafe_actions)}
            icon={<ShieldAlert size={13} />}
            accent="rose"
          />
        </div>
      </div>

      <div>
        <p className="mb-3 font-mono text-[11px] uppercase tracking-widest text-ink-500">Reliability</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricCard label="Payment failures" value={String(data.reliability.payment_failures)} accent="rose" />
          <MetricCard
            label="Successful payments"
            value={String(data.reliability.successful_payments)}
            accent="mint"
          />
          <MetricCard
            label="Duplicates blocked"
            value={String(data.reliability.duplicate_requests_blocked)}
            accent="rose"
          />
          <MetricCard label="Avg retry count" value={data.reliability.average_retry_count.toFixed(2)} />
        </div>
      </div>

      <div className="rounded-xl border border-ink-700 bg-ink-900 p-4">
        <p className="mb-3 font-mono text-[11px] uppercase tracking-widest text-ink-500">Orders &amp; recovery</p>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2838" />
              <XAxis dataKey="name" stroke="#6b7998" fontSize={12} />
              <YAxis stroke="#6b7998" fontSize={12} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "#161d2c", border: "1px solid #2b3548", borderRadius: 8 }} />
              <Bar dataKey="value" fill="#f0a833" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
