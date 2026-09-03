export interface ProductCard {
  product_id: string;
  name: string;
  price: number;
  category: string;
  score: number;
  why_this_product: string;
}

export interface UpsellCard {
  product_id: string;
  name: string;
  price: number;
  why_recommended: string;
  bundle_discount_percent: number;
}

export interface CartLine {
  product_id: string;
  name: string;
  unit_price: number;
  quantity: number;
  line_total: number;
  added_via: string;
}

export interface CartSnapshot {
  cart_id: string;
  items: CartLine[];
  subtotal: number;
}

export interface ChatResponse {
  understood_intent: string;
  reply: string;
  products: ProductCard[];
}

export interface SelectProductResponse {
  cart: CartSnapshot;
  upsell: UpsellCard[];
}

export interface CheckoutPreview {
  subtotal: number;
  discount_amount: number;
  total: number;
  line_items: CartLine[];
}

export interface OrderSummary {
  order_id?: string;
  id?: string;
  status: string;
  total_amount: number;
  razorpay_order_id: string | null;
  subtotal?: number;
  discount_amount?: number;
  retry_count?: number;
  created_at?: string;
  items?: {
    product_name: string;
    quantity: number;
    unit_price: number;
    line_total: number;
  }[];
  payment_attempts?: {
    attempt_number: number;
    provider: string;
    status: string;
    failure_reason: string | null;
    created_at: string;
  }[];
}

export interface AuditEvent {
  event_id: string;
  timestamp: string;
  session_id: string;
  user_id: string | null;
  order_id: string | null;
  event_type: string;
  actor: "USER" | "AI" | "SYSTEM" | "RAZORPAY";
  action: string;
  reason: string;
  status: "OK" | "BLOCKED" | "ERROR";
  metadata: Record<string, unknown>;
}

export interface AnalyticsOverview {
  revenue: {
    total_orders: number;
    successful_payments: number;
    conversion_rate_percent: number;
    total_revenue: number;
    average_order_value: number;
    upsell_acceptance_rate_percent: number;
    incremental_upsell_revenue: number;
  };
  agent: {
    conversations: number;
    product_searches: number;
    recommendations_shown: number;
    blocked_unsafe_actions: number;
  };
  reliability: {
    payment_failures: number;
    successful_payments: number;
    duplicate_requests_blocked: number;
    average_retry_count: number;
  };
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  category: string;
  price: number;
  description: string;
  specs: Record<string, unknown>;
  tags: string[];
  inventory: number;
}

export interface ApiEnvelope<T> {
  ok: boolean;
  data: T;
  error: string | null;
}
