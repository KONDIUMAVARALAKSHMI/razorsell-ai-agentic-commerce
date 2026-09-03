# Architecture

## System diagram

```
                    ┌──────────────────┐
                    │   React Client   │
                    │ (chat, cart,     │
                    │  merchant dash)  │
                    └────────┬─────────┘
                             │ HTTPS / JSON
                             ▼
                    ┌──────────────────┐
                    │   FastAPI API    │
                    │  (app/api/*)     │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌────────────┐ ┌────────────┐ ┌─────────────┐
       │ AI Agent   │ │ Guardrails │ │ Audit Layer │
       │(app/agents)│ │(app/guard- │ │(app/audit)  │
       │            │ │  rails)    │ │             │
       └─────┬──────┘ └─────┬──────┘ └──────┬──────┘
             │              │               │
             ▼              ▼               │
       ┌─────────────────────────┐          │
       │   Deterministic         │◄─────────┘
       │   Services               │
       │ (app/services/*:         │
       │  catalog, cart, checkout,│
       │  scoring, upsell)        │
       └───────┬──────────────────┘
               │
        ┌──────┴────────┐
        ▼               ▼
 ┌─────────────┐  ┌──────────────┐
 │ PostgreSQL  │  │    Redis      │
 │ (source of  │  │ (cache/session│
 │  truth)     │  │  state only)  │
 └──────┬──────┘  └──────────────┘
        │
        ▼
 ┌─────────────────────┐
 │ Payment Provider     │
 │ abstraction          │
 │ (app/payments/*)     │
 ├─────────────────────┤
 │ Razorpay Test Mode   │
 │      or              │
 │ MockPaymentProvider  │
 │ (local, deterministic│
 │  failure simulation) │
 └─────────────────────┘
```

## Request flow for the core demo scenario

```
Customer message
      │
      ▼
POST /api/v1/chat/message
      │
      ├─► AIProvider.extract_intent()          [AI: language understanding only]
      │
      ├─► catalog.search_products()             [deterministic: DB query + scoring]
      │       └─► scoring.rank_products()        [deterministic: weighted formula]
      │
      ├─► AIProvider.explain_recommendation()   [AI: one grounded sentence per result]
      │
      └─► audit.record_event() x3                [PRODUCT_SEARCH, PRODUCT_RECOMMENDATION, AI_DECISION]

Customer selects a product
      │
      ▼
POST /api/v1/chat/select-product
      │
      ├─► cart.add_to_cart()                     [deterministic: validates product exists,
      │                                            inventory available, quantity positive]
      ├─► upsell.get_upsell_candidates()          [deterministic: only merchant-curated
      │                                            ProductRelation rows, capped at 2]
      ├─► AIProvider.explain_upsell()             [AI: one grounded sentence per candidate]
      └─► audit.record_event() x2+                [CART_UPDATED, UPSELL_RECOMMENDATION]

Customer confirms checkout
      │
      ▼
POST /api/v1/checkout/confirm  (confirm=true, idempotency_key=<client-generated>)
      │
      ├─► idempotency check                       [DB unique constraint - duplicate key
      │                                             returns the ORIGINAL order, never a new one]
      ├─► guardrails.enforce_payment_requires_confirmation()
      ├─► checkout.calculate_checkout()           [deterministic: subtotal/discount/total
      │                                             recomputed from live Product.price]
      └─► Order row created (status=CREATED)      [audited: CHECKOUT_STARTED,
                                                     USER_PAYMENT_CONFIRMATION]

Payment
      │
      ▼
POST /api/v1/payments/attempt
      │
      ├─► guardrails.enforce_retry_limit()
      ├─► PaymentProvider.create_order()          [Razorpay Test Mode order, or mock]
      ├─► PaymentProvider.capture_or_verify()     [real verification, or forced demo outcome]
      └─► Order state transition + audit event    [PAYMENT_SUCCESS or PAYMENT_FAILED]
```

## Where AI is used, and where it deliberately is not

| Decision | Owner | Why |
|---|---|---|
| "What does this customer want?" | **AI** | Genuinely a language-understanding problem. |
| "Which products match?" | **Deterministic** (`scoring.py`) | Reproducible, auditable, can't hallucinate a product that isn't in the DB. |
| "Why does this product match?" | **AI** | Turning a score into a one-sentence explanation is a language problem; the facts it can cite come from the deterministic scorer's `reasons` list, so it can't invent a fact either. |
| "What should I cross-sell?" | **Deterministic** (`upsell.py`) | Candidates come only from merchant-curated `ProductRelation` rows. AI has no path to suggest a product outside that set. |
| "Why is this a good add-on?" | **AI** | Same pattern as above — explanation only, over a fact the AI didn't choose. |
| "What's the total?" | **Deterministic** (`checkout.py`) | Money. `calculate_checkout()` doesn't accept an AI-provided price as an argument — it isn't in the function signature. |
| "Is this discount allowed?" | **Deterministic** (`guardrails/policy.py`) | Bounded by `MAX_DISCOUNT_PERCENT`, checked in code, not something the AI is ever asked. |
| "Can this payment go through?" | **Deterministic** (`guardrails/policy.py` + `checkout.py`) | Requires `confirm=true` from an explicit frontend button click. The AI has no tool that can set that flag. |
| "Was this the same request as before?" | **Deterministic** (unique DB constraint on `idempotency_keys.key`) | Idempotency is a database guarantee, not a judgment call. |
| "How many times can we retry?" | **Deterministic** (`MAX_PAYMENT_RETRIES`) | A fixed policy number, not something to reason about per-request. |

## Tool architecture

The agent orchestrator (`app/agents/orchestrator.py`) is **not** a free-form agent loop where a model picks from an open-ended tool list. It's a fixed two-step state machine per turn:

1. Call the AI provider for language understanding or explanation (narrow, single-purpose functions: `extract_intent`, `explain_recommendation`, `explain_upsell`, `conversational_reply`).
2. Call deterministic services for everything else.

The "tools" described in the original brief (`search_products`, `add_to_cart`, `calculate_checkout`, `create_payment_order`, etc.) exist as ordinary Python functions in `app/services/*` and `app/payments/*` — they are called directly by the orchestrator and API layer, not exposed to the LLM as invokable functions it can chain arbitrarily. This is a deliberate, stricter interpretation of "controlled tool layer": the AI never sees a payment-shaped tool at all, so there's no prompt-injection or reasoning-failure path that leads to it calling one.

## Database schema (see `backend/app/models/`)

`users`, `merchants`, `products`, `inventory`, `product_relations`, `carts`, `cart_items`, `orders`, `order_items`, `payment_attempts`, `idempotency_keys`, `agent_sessions`, `agent_messages`, `recommendations`, `audit_events`. Managed via Alembic (`backend/alembic/`); PostgreSQL is the source of truth, Redis is optional cache/session state only and is never authoritative for anything financial.
