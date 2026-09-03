# Security &amp; Safety Model

## The nine guardrail rules

Enforced in `backend/app/guardrails/policy.py`. Every violation raises a typed `GuardrailViolation`, which the API layer converts to an HTTP 403 with the rule name and a plain-English message — never a stack trace — and which the calling service function audits via `app/audit/service.py` **before** the exception propagates (see "Audit persistence on failure" below for why that ordering matters).

| Rule | Enforced by | What it stops |
|---|---|---|
| **1. No payment without explicit confirmation** | `enforce_payment_requires_confirmation()` | `create_order()` raises unless `payment_confirmed=True`, which only ever comes from the frontend's `confirm: true`, which only ever gets set by a real click on "Confirm & Proceed to Payment". The AI has no code path that can set this flag. |
| **2. No AI-set or excessive discount** | `enforce_discount_within_bounds()` | Discount percent is clamped to `[0, MAX_DISCOUNT_PERCENT]` (default 5%). There is no code path where an AI-generated number reaches this parameter — discounts come from merchant-configured `ProductRelation.bundle_discount_percent` or an explicit checkout-preview query param, both server-validated. |
| **3. No hallucinated products** | `enforce_product_exists()` | Every product reference is resolved against the database (`db.get(Product, product_id)`) before any cart/order action. A nonexistent ID is rejected with `RULE_3_NO_HALLUCINATED_PRODUCTS`, not silently ignored or substituted. |
| **4. Max upsell recommendations** | `enforce_max_upsell()` + `upsell.get_upsell_candidates()` | Capped at `MAX_UPSELL_RECOMMENDATIONS` (default 2) per checkout, tracked on `AgentSession.upsell_count`. |
| **5. Retry limit** | `enforce_retry_limit()` | Capped at `MAX_PAYMENT_RETRIES` (default 3). Beyond that, the order moves to `RETRY_LIMIT_REACHED` / `MANUAL_ACTION_REQUIRED` and further retry requests are rejected, audited as `RETRY_BLOCKED`. |
| **6. No secrets exposed** | Config layer (`app/core/config.py`) + audit metadata discipline | Secrets are read once from environment variables and never placed in a response body or an audit event's `metadata` (see `tests/test_audit_logging.py::test_no_secrets_ever_appear_in_audit_metadata`, which asserts this by scanning every audit event after a real payment flow). |
| **7. No direct database access from the AI** | Architectural — see `docs/architecture.md` | The AI provider interface (`app/agents/ai_provider.py`) has four methods, none of which take a database session or a query. It is structurally impossible for the AI layer to run a query, correct or otherwise. |
| **8. Every financial action is audited** | `app/audit/service.py::record_event()` | The single write path for `audit_events`. Checkout creation, payment attempts (success and failure), retries (allowed and blocked), and guardrail rejections all call it. |
| **9. Fail closed on uncertainty** | `app/api/deps.py::guarded()` | Any exception that isn't an explicitly-handled `GuardrailViolation` becomes a generic HTTP 500 with no internal detail leaked — the default behavior on an unexpected error is to refuse the action, not guess at what was intended. |

## Audit persistence on failure — a bug we found and fixed

Early in development, guardrail-blocked actions (e.g. a rejected retry after the limit was reached) logged an audit event via `record_event()` but the surrounding request handler raised an `HTTPException` before ever reaching its own `db.commit()`. Since the ORM session rolls back uncommitted work when the request ends, **the audit trail for blocked actions was silently disappearing** — the one category of event most important to have a record of. Every guardrail-violation code path in `app/services/checkout.py` now explicitly commits immediately after logging the blocked event, before raising. This is covered by `tests/test_audit_logging.py::test_blocked_action_produces_guardrail_blocked_event` and was caught by the same test during development.

## Payment integrity

- **Server-side pricing only.** `calculate_checkout()` has no parameter through which a client-supplied or AI-supplied price could enter. It reads `Product.price` fresh from the database every time.
- **Server-side payment verification.** For Razorpay, `RazorpayPaymentProvider.verify_payment_signature()` recomputes the HMAC-SHA256 signature server-side from the order id, payment id, and the (never-client-visible) key secret, and compares with `hmac.compare_digest` (constant-time). The frontend's reported "it succeeded" is never trusted on its own.
- **Idempotency is a database guarantee, not a convention.** `idempotency_keys.key` has a `unique` constraint. `create_order()` looks up the key before doing anything else; if found, it returns the **existing** order rather than creating a new one. This was verified under a real duplicate-submission scenario in `tests/test_idempotency_and_retries.py` and in `evaluation/scenarios/definitions.py` (`duplicate_request` scenarios).
- **Retry never creates a second provider order.** `initiate_payment()` only calls `PaymentProvider.create_order()` if `order.razorpay_order_id` is still `None`; every subsequent attempt (including retries) reuses the same provider order id. Verified in `tests/test_idempotency_and_retries.py::test_no_duplicate_charge_on_retry`.

## Authentication

The merchant dashboard uses fixed credentials from environment variables (`MERCHANT_DASHBOARD_USERNAME` / `MERCHANT_DASHBOARD_PASSWORD`) and an HMAC-signed, time-limited opaque token (`app/api/merchant.py`). This is **demo-grade**, intentionally: a real identity provider, password hashing with a proper KDF, and per-merchant scoping are out of scope for this build and are called out explicitly in the README's "Known limitations" rather than glossed over.

## Rate limiting

A minimal in-memory, per-IP sliding-window limiter (`app/main.py`) defaults to 300 requests/minute — enough for a full customer journey (search → select → upsell → cart → checkout → payment → retry is roughly 8-10 requests) with headroom for several concurrent demo reviewers, without meaningfully weakening abuse protection for a single-instance hackathon deployment. It is explicitly **not** meant to survive a multi-process production deployment as-is (see "Known limitations" in the README) — the `USE_REDIS` setting exists for exactly this reason but this specific piece isn't wired to it yet.

## Secrets handling

- Read once from environment variables in `app/core/config.py`; never hardcoded.
- `.env` is gitignored; `.env.example` documents every variable with a safe default.
- No secret ever appears in a log line, an API response, or an audit event (see the audit test referenced above).
- Razorpay Test Mode is a convention, not a hard code-level lock: this project has no mechanism that inspects a key and refuses to run if it looks like a live key. Treat "Test Mode keys only" as an operating instruction for anyone deploying this, not a guarantee the code enforces.

## What this system does *not* protect against

Being direct about scope, since a security document that only lists what's covered isn't trustworthy:

- No protection against a compromised database (no encryption at rest configured here).
- No protection against a malicious merchant operator (the merchant dashboard's own auth is the only barrier to seeing all orders/audit data).
- No WAF/DDoS layer — the rate limiter is basic abuse mitigation, not a security boundary.
- No dependency vulnerability scanning is wired into CI (there is no CI in this repository at all — see "Known limitations").
