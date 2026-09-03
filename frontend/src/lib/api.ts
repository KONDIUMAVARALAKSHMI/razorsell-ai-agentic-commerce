import type {
  AnalyticsOverview,
  ApiEnvelope,
  AuditEvent,
  CartSnapshot,
  ChatResponse,
  CheckoutPreview,
  OrderSummary,
  Product,
  SelectProductResponse,
} from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  rule?: string;

  constructor(message: string, status: number, rule?: string) {
    super(message);
    this.status = status;
    this.rule = rule;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  const body = await res.json().catch(() => null);

  if (!res.ok) {
    const detail = body?.detail;
    if (detail && typeof detail === "object") {
      throw new ApiError(detail.message || "Request failed", res.status, detail.rule);
    }
    throw new ApiError(typeof detail === "string" ? detail : "Request failed", res.status);
  }

  if (body && typeof body === "object" && "ok" in body) {
    const envelope = body as ApiEnvelope<T>;
    if (!envelope.ok) {
      throw new ApiError(envelope.error || "Request failed", res.status);
    }
    if ("data" in body) {
      return envelope.data;
    }
  }
  return body as T;
}

export const api = {
  health: () => request<{ status: string; ai_provider: string; payment_provider: string }>("/api/v1/health"),

  listProducts: (category?: string) =>
    request<Product[]>(`/api/v1/catalog/products${category ? `?category=${category}` : ""}`),

  getProduct: (productId: string) => request<Product>(`/api/v1/catalog/products/${productId}`),

  compareProducts: (productIds: string[]) =>
    request<Product[]>("/api/v1/catalog/compare", { method: "POST", body: JSON.stringify(productIds) }),

  sendChatMessage: (sessionId: string, userId: string, message: string) =>
    request<ChatResponse>("/api/v1/chat/message", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, user_id: userId, message }),
    }),

  selectProduct: (sessionId: string, userId: string, productId: string) =>
    request<SelectProductResponse>("/api/v1/chat/select-product", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, user_id: userId, product_id: productId }),
    }),

  getCart: (sessionId: string, userId: string) =>
    request<CartSnapshot>(`/api/v1/cart/${sessionId}?user_id=${encodeURIComponent(userId)}`),

  addToCart: (sessionId: string, userId: string, productId: string, quantity = 1) =>
    request<CartSnapshot>("/api/v1/cart/add", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, user_id: userId, product_id: productId, quantity }),
    }),

  removeFromCart: (sessionId: string, userId: string, productId: string) =>
    request<CartSnapshot>("/api/v1/cart/remove", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, user_id: userId, product_id: productId }),
    }),

  updateCartQuantity: (sessionId: string, userId: string, productId: string, quantity: number) =>
    request<CartSnapshot>("/api/v1/cart/update-quantity", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, user_id: userId, product_id: productId, quantity }),
    }),

  upsellDecision: (sessionId: string, userId: string, productId: string, accept: boolean) =>
    request<CartSnapshot>("/api/v1/cart/upsell-decision", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, user_id: userId, product_id: productId, accept }),
    }),

  checkoutPreview: (sessionId: string, userId: string, discountPercent = 0) =>
    request<CheckoutPreview>(
      `/api/v1/checkout/preview?session_id=${sessionId}&user_id=${userId}&discount_percent=${discountPercent}`
    ),

  confirmCheckout: (sessionId: string, userId: string, idempotencyKey: string, discountPercent = 0) =>
    request<OrderSummary>("/api/v1/checkout/confirm", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        user_id: userId,
        confirm: true,
        discount_percent: discountPercent,
        idempotency_key: idempotencyKey,
      }),
    }),

  attemptPayment: (orderId: string, simulatedOutcome?: string) =>
    request<{ order_status: string; attempt_status: string; failure_reason: string | null; retry_count: number }>(
      "/api/v1/payments/attempt",
      { method: "POST", body: JSON.stringify({ order_id: orderId, simulated_outcome: simulatedOutcome }) }
    ),

  retryPayment: (orderId: string) =>
    request<{ status: string }>("/api/v1/payments/retry", {
      method: "POST",
      body: JSON.stringify({ order_id: orderId }),
    }),

  getOrder: (orderId: string) => request<OrderSummary>(`/api/v1/orders/${orderId}`),

  listOrders: (limit = 50) => request<OrderSummary[]>(`/api/v1/orders?limit=${limit}`),

  listAuditEvents: (params: Record<string, string | undefined> = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][]
    ).toString();
    return request<AuditEvent[]>(`/api/v1/audit/events${query ? `?${query}` : ""}`);
  },

  analyticsOverview: () => request<AnalyticsOverview>("/api/v1/analytics/overview"),

  merchantLogin: (username: string, password: string) =>
    request<{ token: string; expires_in: number }>("/api/v1/merchant/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
};
