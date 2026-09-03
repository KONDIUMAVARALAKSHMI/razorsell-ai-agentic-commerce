interface StatusBadgeProps {
  status: string;
}

const STATUS_STYLES: Record<string, string> = {
  SUCCESS: "bg-mint-success-dim text-mint-success border-mint-success/30",
  OK: "bg-mint-success-dim text-mint-success border-mint-success/30",
  CREATED: "bg-ink-700 text-ink-200 border-ink-600",
  PAYMENT_PENDING: "bg-amber-signal-dim text-amber-signal border-amber-signal/30",
  RETRY_ALLOWED: "bg-amber-signal-dim text-amber-signal border-amber-signal/30",
  FAILED: "bg-rose-failure-dim text-rose-failure border-rose-failure/30",
  ERROR: "bg-rose-failure-dim text-rose-failure border-rose-failure/30",
  BLOCKED: "bg-rose-failure-dim text-rose-failure border-rose-failure/30",
  RETRY_LIMIT_REACHED: "bg-rose-failure-dim text-rose-failure border-rose-failure/30",
  MANUAL_ACTION_REQUIRED: "bg-rose-failure-dim text-rose-failure border-rose-failure/30",
  CANCELLED: "bg-ink-700 text-ink-400 border-ink-600",
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const style = STATUS_STYLES[status] || "bg-ink-700 text-ink-300 border-ink-600";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-wide ${style}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status.replace(/_/g, " ")}
    </span>
  );
}
