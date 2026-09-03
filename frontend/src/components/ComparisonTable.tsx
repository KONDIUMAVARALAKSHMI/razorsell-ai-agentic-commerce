import { X } from "lucide-react";
import { formatInr } from "../lib/format";
import type { Product } from "../types/api";

interface Props {
  products: Product[];
  onClose: () => void;
}

export default function ComparisonTable({ products, onClose }: Props) {
  if (products.length === 0) return null;

  const specKeys = Array.from(new Set(products.flatMap((p) => Object.keys(p.specs || {}))));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="max-h-[85vh] w-full max-w-3xl overflow-hidden rounded-2xl border border-ink-700 bg-ink-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-ink-700 px-5 py-4">
          <p className="font-display text-base font-semibold">Compare products</p>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-100" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="ledger-scroll max-h-[70vh] overflow-auto p-5">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="w-32 text-left font-mono text-[11px] uppercase tracking-wide text-ink-500">Spec</th>
                {products.map((p) => (
                  <th key={p.id} className="px-3 pb-3 text-left">
                    <p className="font-display text-[13px] font-semibold text-ink-100">{p.name}</p>
                    <p className="mt-1 font-mono text-sm text-amber-signal">{formatInr(p.price)}</p>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {specKeys.map((key) => (
                <tr key={key} className="border-t border-ink-700">
                  <td className="py-2 pr-3 font-mono text-[11px] uppercase tracking-wide text-ink-500">{key}</td>
                  {products.map((p) => (
                    <td key={p.id} className="px-3 py-2 text-ink-200">
                      {String(p.specs?.[key] ?? "-")}
                    </td>
                  ))}
                </tr>
              ))}
              <tr className="border-t border-ink-700">
                <td className="py-2 pr-3 font-mono text-[11px] uppercase tracking-wide text-ink-500">In stock</td>
                {products.map((p) => (
                  <td key={p.id} className="px-3 py-2 text-ink-200">
                    {p.inventory > 0 ? `${p.inventory} units` : "Out of stock"}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
