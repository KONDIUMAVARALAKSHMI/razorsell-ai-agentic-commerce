import { Minus, Plus, ShoppingCart, Trash2 } from "lucide-react";
import { formatInr } from "../lib/format";
import type { CartSnapshot } from "../types/api";

interface Props {
  cart: CartSnapshot | null;
  onUpdateQuantity: (productId: string, quantity: number) => void;
  onRemove: (productId: string) => void;
  onCheckout: () => void;
  checkoutDisabled?: boolean;
}

export default function CartPanel({ cart, onUpdateQuantity, onRemove, onCheckout, checkoutDisabled }: Props) {
  const items = cart?.items || [];

  return (
    <div className="flex h-full flex-col rounded-xl border border-ink-700 bg-ink-900">
      <div className="flex items-center gap-2 border-b border-ink-700 px-4 py-3">
        <ShoppingCart size={16} className="text-ink-300" />
        <p className="font-display text-sm font-semibold">Cart</p>
        <span className="ml-auto font-mono text-xs text-ink-400">{items.length} item(s)</span>
      </div>

      <div className="ledger-scroll flex-1 overflow-y-auto p-3">
        {items.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-1.5 py-10 text-center">
            <p className="text-sm text-ink-400">Your cart is empty.</p>
            <p className="text-xs text-ink-500">Ask the assistant for a product to get started.</p>
          </div>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {items.map((item) => (
              <li key={item.product_id} className="rounded-lg border border-ink-700 bg-ink-800 p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-[13px] font-medium leading-snug text-ink-100">{item.name}</p>
                  <button
                    onClick={() => onRemove(item.product_id)}
                    className="text-ink-500 hover:text-rose-failure"
                    aria-label={`Remove ${item.name}`}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
                {item.added_via === "upsell_accept" && (
                  <p className="mt-0.5 font-mono text-[10px] uppercase tracking-wide text-amber-signal">
                    added via upsell
                  </p>
                )}
                <div className="mt-2 flex items-center justify-between">
                  <div className="flex items-center gap-1 rounded-md border border-ink-600">
                    <button
                      onClick={() => onUpdateQuantity(item.product_id, item.quantity - 1)}
                      className="p-1.5 text-ink-300 hover:text-ink-100"
                      aria-label="Decrease quantity"
                    >
                      <Minus size={12} />
                    </button>
                    <span className="w-5 text-center font-mono text-xs">{item.quantity}</span>
                    <button
                      onClick={() => onUpdateQuantity(item.product_id, item.quantity + 1)}
                      className="p-1.5 text-ink-300 hover:text-ink-100"
                      aria-label="Increase quantity"
                    >
                      <Plus size={12} />
                    </button>
                  </div>
                  <p className="font-mono text-sm text-ink-100">{formatInr(item.line_total)}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-ink-700 p-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm text-ink-300">Subtotal</span>
          <span className="font-mono text-base font-medium text-ink-100">{formatInr(cart?.subtotal || 0)}</span>
        </div>
        <button
          onClick={onCheckout}
          disabled={items.length === 0 || checkoutDisabled}
          className="w-full rounded-lg bg-amber-signal py-2.5 text-sm font-semibold text-ink-950 transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
        >
          Review checkout
        </button>
      </div>
    </div>
  );
}
