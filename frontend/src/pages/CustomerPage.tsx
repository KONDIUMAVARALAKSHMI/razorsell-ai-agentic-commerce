import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { getSessionId, getUserId, newIdempotencyKey } from "../lib/session";
import ChatMessage from "../components/ChatMessage";
import ProductCard from "../components/ProductCard";
import UpsellCard from "../components/UpsellCard";
import CartPanel from "../components/CartPanel";
import CheckoutConfirmModal from "../components/CheckoutConfirmModal";
import PaymentResultPanel from "../components/PaymentResultPanel";
import ComparisonTable from "../components/ComparisonTable";
import type {
  CartSnapshot,
  CheckoutPreview,
  OrderSummary,
  Product,
  ProductCard as ProductCardType,
  UpsellCard as UpsellCardType,
} from "../types/api";

interface Turn {
  id: string;
  role: "user" | "assistant";
  content: string;
  products?: ProductCardType[];
  upsell?: UpsellCardType[];
}

const SUGGESTED_PROMPTS = [
  "I need a laptop under 70000 for coding and gaming, something portable",
  "Looking for a gaming laptop under 100000",
  "Affordable laptop under 40000 for college",
  "Wireless mouse under 3000 for coding",
];

export default function CustomerPage() {
  const [sessionId] = useState(getSessionId());
  const [userId] = useState(getUserId());
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [cart, setCart] = useState<CartSnapshot | null>(null);
  const [upsellDecisions, setUpsellDecisions] = useState<Record<string, "accepted" | "rejected">>({});
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [compareProducts, setCompareProducts] = useState<Product[] | null>(null);
  const [checkoutPreview, setCheckoutPreview] = useState<CheckoutPreview | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [activeOrder, setActiveOrder] = useState<OrderSummary | null>(null);
  const [orderBusy, setOrderBusy] = useState(false);
  const [providerInfo, setProviderInfo] = useState<{ ai: string; payment: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.health().then((h) => setProviderInfo({ ai: h.ai_provider, payment: h.payment_provider })).catch(() => {});
    refreshCart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  async function refreshCart() {
    try {
      const snapshot = await api.getCart(sessionId, userId);
      setCart(snapshot);
    } catch {
      // A brand-new session has no cart row yet - that's fine, not an error.
    }
  }

  async function sendMessage(message: string) {
    if (!message.trim() || sending) return;
    setError(null);
    setInput("");
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "user", content: message }]);
    setSending(true);
    try {
      const res = await api.sendChatMessage(sessionId, userId, message);
      setTurns((t) => [
        ...t,
        { id: crypto.randomUUID(), role: "assistant", content: res.reply, products: res.products },
      ]);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Something went wrong reaching the assistant.";
      setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content: msg }]);
    } finally {
      setSending(false);
    }
  }

  async function handleAddProduct(productId: string) {
    setError(null);
    try {
      const res = await api.selectProduct(sessionId, userId, productId);
      setCart(res.cart);
      if (res.upsell.length > 0) {
        setTurns((t) => [
          ...t,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: "Added to your cart. Here's something that might go well with it:",
            upsell: res.upsell,
          },
        ]);
      } else {
        setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content: "Added to your cart." }]);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not add that item.");
    }
  }

  async function handleUpsellDecision(productId: string, accept: boolean) {
    try {
      const snapshot = await api.upsellDecision(sessionId, userId, productId, accept);
      setCart(snapshot);
      setUpsellDecisions((d) => ({ ...d, [productId]: accept ? "accepted" : "rejected" }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not record that decision.");
    }
  }

  function toggleCompare(productId: string) {
    setCompareIds((ids) =>
      ids.includes(productId) ? ids.filter((id) => id !== productId) : ids.length < 3 ? [...ids, productId] : ids
    );
  }

  async function handleCompare() {
    if (compareIds.length < 2) return;
    try {
      const products = await api.compareProducts(compareIds);
      setCompareProducts(products);
    } catch {
      setError("Could not load comparison.");
    }
  }

  async function handleUpdateQuantity(productId: string, quantity: number) {
    try {
      const snapshot =
        quantity <= 0
          ? await api.removeFromCart(sessionId, userId, productId)
          : await api.updateCartQuantity(sessionId, userId, productId, quantity);
      setCart(snapshot);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update quantity.");
    }
  }

  async function handleRemove(productId: string) {
    try {
      const snapshot = await api.removeFromCart(sessionId, userId, productId);
      setCart(snapshot);
    } catch {
      setError("Could not remove item.");
    }
  }

  async function handleOpenCheckout() {
    try {
      const preview = await api.checkoutPreview(sessionId, userId);
      setCheckoutPreview(preview);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load checkout preview.");
    }
  }

  async function handleConfirmCheckout() {
    setCheckoutLoading(true);
    setError(null);
    try {
      const idemKey = newIdempotencyKey();
      const order = await api.confirmCheckout(sessionId, userId, idemKey);
      setCheckoutPreview(null);
      // Initial attempt triggers simulated failure to demonstrate the mandatory
      // failure recovery, retry policy, and idempotency features for the demo.
      const attempt = await api.attemptPayment(order.order_id!, "FAILURE");
      const fullOrder = await api.getOrder(order.order_id!);
      setActiveOrder(fullOrder);
      void attempt;
      await refreshCart();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Checkout could not be completed.");
      setCheckoutPreview(null);
    } finally {
      setCheckoutLoading(false);
    }
  }

  async function handleSimulate(outcome: "SUCCESS" | "FAILURE" | "TIMEOUT" | "DUPLICATE_REQUEST") {
    if (!activeOrder?.order_id && !activeOrder?.id) return;
    const orderId = (activeOrder.order_id || activeOrder.id)!;
    setOrderBusy(true);
    try {
      await api.attemptPayment(orderId, outcome);
      const fullOrder = await api.getOrder(orderId);
      setActiveOrder(fullOrder);
    } finally {
      setOrderBusy(false);
    }
  }

  async function handleRetry() {
    if (!activeOrder?.order_id && !activeOrder?.id) return;
    const orderId = (activeOrder.order_id || activeOrder.id)!;
    setOrderBusy(true);
    try {
      await api.retryPayment(orderId);
      await api.attemptPayment(orderId, "SUCCESS");
      const fullOrder = await api.getOrder(orderId);
      setActiveOrder(fullOrder);
    } finally {
      setOrderBusy(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 p-4 sm:p-6 lg:grid-cols-[1fr_340px]">
      <section className="flex h-[calc(100vh-96px)] flex-col rounded-xl border border-ink-700 bg-ink-900">
        <div ref={scrollRef} className="ledger-scroll flex-1 space-y-4 overflow-y-auto p-4 sm:p-6">
          {turns.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
              <p className="font-display text-lg font-semibold text-ink-100">What are you shopping for?</p>
              <p className="max-w-sm text-sm text-ink-400">
                Tell the assistant your budget and what you'll use it for - it searches the real catalog and
                explains every recommendation.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTED_PROMPTS.map((p) => (
                  <button
                    key={p}
                    onClick={() => sendMessage(p)}
                    className="rounded-full border border-ink-600 px-3 py-1.5 text-xs text-ink-300 hover:border-amber-signal hover:text-amber-signal"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn) => (
            <div key={turn.id} className="flex flex-col gap-3">
              <ChatMessage role={turn.role} content={turn.content} />
              {turn.products && turn.products.length > 0 && (
                <div className="ml-9 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {turn.products.map((p) => (
                    <ProductCard
                      key={p.product_id}
                      product={p}
                      onAdd={handleAddProduct}
                      onToggleCompare={toggleCompare}
                      isComparing={compareIds.includes(p.product_id)}
                    />
                  ))}
                </div>
              )}
              {turn.upsell && turn.upsell.length > 0 && (
                <div className="ml-9 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {turn.upsell.map((u) => (
                    <UpsellCard
                      key={u.product_id}
                      upsell={u}
                      onDecide={handleUpsellDecision}
                      decided={upsellDecisions[u.product_id]}
                    />
                  ))}
                </div>
              )}
            </div>
          ))}

          {sending && (
            <ChatMessage role="assistant" content="Searching the catalog..." />
          )}
        </div>

        {compareIds.length >= 2 && (
          <div className="flex items-center justify-between border-t border-ink-700 bg-ink-800 px-4 py-2">
            <span className="text-xs text-ink-300">{compareIds.length} products selected to compare</span>
            <button onClick={handleCompare} className="text-xs font-medium text-amber-signal hover:underline">
              Compare now
            </button>
          </div>
        )}

        {error && (
          <div className="border-t border-rose-failure/30 bg-rose-failure-dim px-4 py-2 text-xs text-rose-failure">
            {error}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage(input);
          }}
          className="flex items-center gap-2 border-t border-ink-700 p-3"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. laptop under 70000 for coding and gaming"
            className="flex-1 rounded-lg border border-ink-600 bg-ink-800 px-3.5 py-2.5 text-sm text-ink-100 placeholder:text-ink-500 focus:border-amber-signal"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-signal text-ink-950 disabled:opacity-40"
            aria-label="Send"
          >
            <Send size={16} />
          </button>
        </form>
      </section>

      <aside className="h-[calc(100vh-96px)]">
        <CartPanel
          cart={cart}
          onUpdateQuantity={handleUpdateQuantity}
          onRemove={handleRemove}
          onCheckout={handleOpenCheckout}
        />
      </aside>

      <CheckoutConfirmModal
        preview={checkoutPreview}
        loading={checkoutLoading}
        onConfirm={handleConfirmCheckout}
        onClose={() => setCheckoutPreview(null)}
      />

      {activeOrder && (
        <PaymentResultPanel
          order={activeOrder}
          onSimulate={handleSimulate}
          onRetry={handleRetry}
          onClose={() => setActiveOrder(null)}
          isMockProvider={providerInfo?.payment !== "razorpay"}
          busy={orderBusy}
        />
      )}

      {compareProducts && (
        <ComparisonTable products={compareProducts} onClose={() => setCompareProducts(null)} />
      )}
    </div>
  );
}
