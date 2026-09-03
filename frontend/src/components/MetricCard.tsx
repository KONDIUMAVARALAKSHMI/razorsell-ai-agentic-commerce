import type { ReactNode } from "react";

interface Props {
  label: string;
  value: string;
  icon?: ReactNode;
  accent?: "amber" | "mint" | "rose" | "violet" | "default";
}

const ACCENTS: Record<string, string> = {
  amber: "text-amber-signal",
  mint: "text-mint-success",
  rose: "text-rose-failure",
  violet: "text-violet-ai",
  default: "text-ink-100",
};

export default function MetricCard({ label, value, icon, accent = "default" }: Props) {
  return (
    <div className="flex flex-col gap-1.5 rounded-xl border border-ink-700 bg-ink-900 p-4">
      <div className="flex items-center gap-1.5 text-ink-400">
        {icon}
        <span className="font-mono text-[10px] uppercase tracking-widest">{label}</span>
      </div>
      <span className={`font-display text-2xl font-semibold ${ACCENTS[accent]}`}>{value}</span>
    </div>
  );
}
