import { Check, X } from "lucide-react";
import { formatInr } from "../lib/format";
import type { UpsellCard as UpsellCardType } from "../types/api";

interface Props {
  upsell: UpsellCardType;
  onDecide: (productId: string, accept: boolean) => void;
  decided?: "accepted" | "rejected";
}

export default function UpsellCard({ upsell, onDecide, decided }: Props) {
  return (
    <div className="flex flex-col gap-2.5 rounded-xl border border-dashed border-amber-signal/40 bg-ink-900 p-4">
      <p className="font-mono text-[10px] uppercase tracking-widest text-amber-signal">Suggested add-on</p>
      <div className="flex items-start justify-between gap-2">
        <p className="font-display text-sm font-semibold text-ink-100">{upsell.name}</p>
        <p className="whitespace-nowrap font-mono text-sm text-amber-signal">{formatInr(upsell.price)}</p>
      </div>
      <p className="text-[13px] leading-snug text-ink-300">{upsell.why_recommended}</p>
      {upsell.bundle_discount_percent > 0 && (
        <p className="font-mono text-[11px] text-mint-success">
          {upsell.bundle_discount_percent}% bundle discount applies at checkout
        </p>
      )}
      {decided ? (
        <p className="font-mono text-[11px] uppercase tracking-wide text-ink-400">
          {decided === "accepted" ? "Added to cart" : "Not added"}
        </p>
      ) : (
        <div className="flex gap-2">
          <button
            onClick={() => onDecide(upsell.product_id, true)}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-mint-success/90 px-3 py-1.5 text-sm font-medium text-ink-950 hover:opacity-90"
          >
            <Check size={14} />
            Add it
          </button>
          <button
            onClick={() => onDecide(upsell.product_id, false)}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-ink-600 px-3 py-1.5 text-sm font-medium text-ink-300 hover:border-ink-400"
          >
            <X size={14} />
            No thanks
          </button>
        </div>
      )}
    </div>
  );
}
