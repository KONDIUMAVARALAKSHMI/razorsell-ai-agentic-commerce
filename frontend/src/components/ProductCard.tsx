import { Plus, Sparkles } from "lucide-react";
import { formatInr } from "../lib/format";
import type { ProductCard as ProductCardType } from "../types/api";

interface Props {
  product: ProductCardType;
  onAdd: (productId: string) => void;
  onToggleCompare?: (productId: string) => void;
  isComparing?: boolean;
  disabled?: boolean;
}

export default function ProductCard({ product, onAdd, onToggleCompare, isComparing, disabled }: Props) {
  return (
    <div className="flex w-full flex-col gap-3 rounded-xl border border-ink-700 bg-ink-900 p-4 transition-colors hover:border-ink-500">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-display text-[15px] font-semibold text-ink-100">{product.name}</p>
          <p className="mt-0.5 font-mono text-[11px] uppercase tracking-wide text-ink-400">{product.category}</p>
        </div>
        <p className="whitespace-nowrap font-mono text-base font-medium text-amber-signal">
          {formatInr(product.price)}
        </p>
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-violet-ai/20 bg-violet-ai-dim/30 p-2.5">
        <Sparkles size={14} className="mt-0.5 shrink-0 text-violet-ai" />
        <p className="text-[13px] leading-snug text-ink-200">{product.why_this_product}</p>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => onAdd(product.product_id)}
          disabled={disabled}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-amber-signal px-3 py-2 text-sm font-medium text-ink-950 transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Plus size={15} />
          Add to cart
        </button>
        {onToggleCompare && (
          <button
            onClick={() => onToggleCompare(product.product_id)}
            className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
              isComparing
                ? "border-violet-ai bg-violet-ai-dim text-violet-ai"
                : "border-ink-600 text-ink-300 hover:border-ink-400"
            }`}
          >
            Compare
          </button>
        )}
      </div>
    </div>
  );
}
