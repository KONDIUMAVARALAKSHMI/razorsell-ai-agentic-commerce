import { AlertTriangle, CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { formatInr } from "../lib/format";
import type { OrderSummary } from "../types/api";
import StatusBadge from "./StatusBadge";

interface Props {
  order: OrderSummary;
  onSimulate: (outcome: "SUCCESS" | "FAILURE" | "TIMEOUT" | "DUPLICATE_REQUEST") => void;
  onRetry: () => void;
  onClose: () => void;
  isMockProvider: boolean;
  busy: boolean;
}

export default function PaymentResultPanel({ order, onSimulate, onRetry, onClose, isMockProvider, busy }: Props) {
  const status = order.status;
  const attempts = order.payment_attempts || [];
  const lastAttempt = attempts[attempts.length - 1];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-ink-700 bg-ink-900 shadow-2xl">
        <div className="flex flex-col items-center gap-3 border-b border-ink-700 px-6 py-6 text-center">
          {status === "SUCCESS" && <CheckCircle2 size={40} className="text-mint-success" />}
          {(status === "RETRY_ALLOWED" || status === "FAILED") && (
            <AlertTriangle size={40} className="text-amber-signal" />
          )}
          {(status === "RETRY_LIMIT_REACHED" || status === "MANUAL_ACTION_REQUIRED") && (
            <XCircle size={40} className="text-rose-failure" />
          )}
          {status === "PAYMENT_PENDING" && <RefreshCw size={40} className="animate-spin text-ink-300" />}

          <div>
            <p className="font-display text-lg font-semibold">
              {status === "SUCCESS" && "Payment successful"}
              {(status === "RETRY_ALLOWED" || status === "FAILED") && "Payment attempt unsuccessful"}
              {status === "RETRY_LIMIT_REACHED" && "Retry limit reached"}
              {status === "MANUAL_ACTION_REQUIRED" && "Manual action required"}
              {status === "PAYMENT_PENDING" && "Processing payment"}
            </p>
            <p className="mt-1 font-mono text-sm text-ink-400">{formatInr(order.total_amount)}</p>
          </div>
          <StatusBadge status={status} />
        </div>

        <div className="px-6 py-4">
          {status === "SUCCESS" ? (
            <p className="text-center text-sm text-ink-300">
              Your order is confirmed. No additional payment has been initiated.
            </p>
          ) : status === "RETRY_LIMIT_REACHED" ? (
            <p className="text-center text-sm text-ink-300">
              The maximum number of retry attempts has been reached. Your order is still safe and no duplicate
              charge has occurred - please contact support to complete payment manually.
            </p>
          ) : (
            <p className="text-center text-sm text-ink-300">
              {lastAttempt?.failure_reason ||
                "The payment attempt was unsuccessful. No additional payment has been initiated."}{" "}
              Your order is still safe. Retry {order.retry_count ?? 0}/3 used.
            </p>
          )}

          {attempts.length > 0 && (
            <div className="mt-4 rounded-lg border border-ink-700 bg-ink-800 p-3">
              <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-ink-500">Attempt history</p>
              <ul className="flex flex-col gap-1.5">
                {attempts.map((a) => (
                  <li key={a.attempt_number} className="flex items-center justify-between text-xs">
                    <span className="font-mono text-ink-400">#{a.attempt_number}</span>
                    <StatusBadge status={a.status} />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-2 px-6 pb-6">
          {(status === "RETRY_ALLOWED" || status === "FAILED") && (
            <button
              onClick={onRetry}
              disabled={busy}
              className="flex items-center justify-center gap-2 rounded-lg bg-amber-signal py-2.5 text-sm font-semibold text-ink-950 hover:opacity-90 disabled:opacity-50"
            >
              <RefreshCw size={15} />
              Retry payment
            </button>
          )}
          {status === "SUCCESS" || status === "RETRY_LIMIT_REACHED" || status === "MANUAL_ACTION_REQUIRED" ? (
            <button
              onClick={onClose}
              className="rounded-lg border border-ink-600 py-2.5 text-sm font-medium text-ink-300 hover:border-ink-400"
            >
              Done
            </button>
          ) : (
            <button
              onClick={onClose}
              className="rounded-lg border border-ink-600 py-2.5 text-sm font-medium text-ink-300 hover:border-ink-400"
            >
              Close
            </button>
          )}

          {isMockProvider && ["PAYMENT_PENDING", "RETRY_ALLOWED", "CREATED", "FAILED"].includes(status) && (
            <div className="mt-1 rounded-lg border border-dashed border-ink-600 p-3">
              <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-ink-500">
                Demo: simulate outcome (mock provider)
              </p>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => onSimulate("SUCCESS")}
                  className="rounded-md border border-mint-success/40 px-2 py-1.5 text-xs text-mint-success hover:bg-mint-success-dim"
                >
                  Force success
                </button>
                <button
                  onClick={() => onSimulate("FAILURE")}
                  className="rounded-md border border-rose-failure/40 px-2 py-1.5 text-xs text-rose-failure hover:bg-rose-failure-dim"
                >
                  Force failure
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
