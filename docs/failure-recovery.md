# Failure Recovery

## Order state machine

Enforced in `backend/app/services/checkout.py`; states are the closed set defined in `backend/app/models/orders.py::ORDER_STATES`.

```
CREATED
  │  (first payment attempt)
  ▼
PAYMENT_PENDING
  │
  ├─► SUCCESS
  │
  └─► FAILED ──► RETRY_ALLOWED ──► PAYMENT_PENDING  (loop, up to MAX_PAYMENT_RETRIES)
                       │
                       └─► RETRY_LIMIT_REACHED ──► MANUAL_ACTION_REQUIRED
```

A retry request is only accepted from `RETRY_ALLOWED` or `FAILED`. Requesting a retry from any other state (including `RETRY_LIMIT_REACHED`, or an order that never failed) is rejected with `INVALID_STATE_TRANSITION` and audited as `RETRY_BLOCKED` — this is exercised directly in `tests/test_idempotency_and_retries.py::test_retry_blocked_after_limit_reached`.

## Real vs. simulated failure

This distinction is load-bearing for the whole story, so it's stated plainly in three places: this document, the README, and the payment result panel's UI copy itself ("Razorpay Test Mode - no real money moves" / "Demo: simulate outcome (mock provider)").

- **`RazorpayPaymentProvider`** (`app/payments/razorpay_provider.py`) talks to Razorpay's real Test Mode API. A "failure" here is Razorpay's test environment genuinely rejecting a test card or the handoff failing — not something this codebase fabricates.
- **`MockPaymentProvider`** (`app/payments/mock_provider.py`) is a **local, deterministic simulation** that exists specifically so the failure-recovery story (and the evaluation suite) can be demonstrated and tested without any external dependency. It accepts a `simulated_outcome` of `SUCCESS`, `FAILURE`, `TIMEOUT`, or `DUPLICATE_REQUEST` and returns a correspondingly labeled result (e.g. `"Simulated failure: card declined by issuing bank (demo)."`) — the word "Simulated" is baked into the failure reason string itself, so it can never be mistaken for a real gateway response even out of context.

Both implement the same `PaymentProvider` interface (`app/payments/base.py`), so the entire checkout/retry/audit code path is identical regardless of which one is active — the only thing that changes is where `capture_or_verify()` gets its answer from.

## The mandatory failure demo

Walking through what actually happens, backed by the exact test that verifies it (`tests/test_integration_flows.py::test_payment_failure_then_successful_retry`):

1. Customer completes checkout normally; `POST /api/v1/checkout/confirm` creates an `Order` in `CREATED`.
2. `POST /api/v1/payments/attempt` with `simulated_outcome=FAILURE` (in the UI: the merchant/reviewer clicks "Force failure" in the payment result panel) → provider returns a failed result → order moves to `RETRY_ALLOWED`, `retry_count` becomes 1, a `PAYMENT_FAILED` audit event is recorded with the failure reason.
3. The customer sees: *"The payment attempt was unsuccessful. No additional payment has been initiated. Your order is still safe. Retry 1/3 used."*
4. `POST /api/v1/payments/retry` → guardrail checks the order is in a retryable state → order moves to `PAYMENT_PENDING`, a `RETRY_REQUESTED` audit event is recorded. **No new provider order is created** — `initiate_payment()` only calls `create_order()` on the provider if `order.razorpay_order_id` is still unset, and by this point it's already set from step 2.
5. `POST /api/v1/payments/attempt` with `simulated_outcome=SUCCESS` → order moves to `SUCCESS`, `retry_count` resets to 0, a `PAYMENT_SUCCESS` audit event is recorded.
6. Exactly one `Order` row, one provider order id, and two `PaymentAttempt` rows (`FAILED` then `SUCCESS`) exist for this checkout — never two orders, never two charges.

## Duplicate request prevention

Covered by `tests/test_idempotency_and_retries.py::TestIdempotency` and the `duplicate_request` scenarios in the evaluation suite.

The client generates an `idempotency_key` once, when the checkout confirmation screen is shown, and sends the same key on every retry of that submission (network retry, accidental double-click, etc.). `POST /api/v1/checkout/confirm` looks the key up in the `idempotency_keys` table (unique constraint on `key`) **before** touching the cart at all:

- Same key seen again → the original `Order` is returned. No new order, no new cart mutation.
- No key (or a genuinely new key) → treated as a new checkout attempt.

This was deliberately redesigned partway through development: an earlier version derived the idempotency key from `cart.id`, which broke the moment a cart transitioned to `checked_out` status and a retried request built a fresh (empty) cart — the "duplicate" check silently missed because the key had changed underneath it. The fix (client-supplied, stable-per-attempt key) and the bug it replaced are both described in `docs/engineering-decisions.md`.

## Out-of-stock / insufficient inventory

Not a payment failure, but the same "fail closed, explain clearly" pattern: `enforce_inventory_available()` blocks the add-to-cart action itself with `INVENTORY_CHECK` before anything downstream (checkout, payment) is ever reached. Covered by `tests/test_cart_and_inventory.py` and the `out_of_stock` / `insufficient_inventory` evaluation scenarios.

## What "safe" means concretely, end to end

By the end of the failure→retry→recovery flow above, everything holds simultaneously:

- One `Order` row.
- One provider-side order id.
- Two audited `PaymentAttempt`s, correctly ordered and correctly statused.
- `retry_count` accurately reflects real attempts, reset to zero on eventual success.
- The full sequence is queryable via `GET /api/v1/audit/events?order_id=...` and renders in the merchant dashboard's Failure Center and Audit Trail tabs, unfiltered and unedited.
