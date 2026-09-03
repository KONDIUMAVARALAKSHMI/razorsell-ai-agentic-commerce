import { Lock, ShieldCheck, X } from "lucide-react";
import { formatInr } from "../lib/format";
import type { CheckoutPreview } from "../types/api";

interface Props {
  preview: CheckoutPreview | null;
  loading: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export default function CheckoutConfirmModal({ preview, loading, onConfirm, onClose }: Props) {
  if (!preview) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-ink-700 bg-ink-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-ink-700 px-5 py-4">
          <p className="font-display text-base font-semibold">Order summary</p>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-100" aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="px-5 py-4">
          <ul className="flex flex-col gap-2 border-b border-ink-700 pb-3">
            {preview.line_items.map((item) => (
              <li key={item.product_id} className="flex items-center justify-between text-sm">
                <span className="text-ink-200">
                  {item.name} <span className="text-ink-500">x{item.quantity}</span>
                </span>
                <span className="font-mono text-ink-100">{formatInr(item.line_total)}</span>
              </li>
            ))}
          </ul>

          <div className="flex flex-col gap-1.5 py-3">
            <div className="flex items-center justify-between text-sm text-ink-300">
              <span>Subtotal</span>
              <span className="font-mono">{formatInr(preview.subtotal)}</span>
            </div>
            {preview.discount_amount > 0 && (
              <div className="flex items-center justify-between text-sm text-mint-success">
                <span>Discount</span>
                <span className="font-mono">-{formatInr(preview.discount_amount)}</span>
              </div>
            )}
            <div className="flex items-center justify-between border-t border-ink-700 pt-2 text-base font-semibold">
              <span>Total</span>
              <span className="font-mono text-amber-signal">{formatInr(preview.total)}</span>
            </div>
          </div>

          <div className="mt-2 flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-800 px-3 py-2">
            <Lock size={13} className="text-ink-400" />
            <p className="font-mono text-[11px] text-ink-400">Razorpay Test Mode - no real money moves</p>
          </div>
        </div>

        <div className="flex flex-col gap-2 px-5 pb-5">
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex items-center justify-center gap-2 rounded-lg bg-amber-signal py-2.5 text-sm font-semibold text-ink-950 transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ShieldCheck size={16} />
            {loading ? "Confirming..." : "Confirm & proceed to payment"}
          </button>
          <button
            onClick={onClose}
            className="rounded-lg border border-ink-600 py-2.5 text-sm font-medium text-ink-300 hover:border-ink-400"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
