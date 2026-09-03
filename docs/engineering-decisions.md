# Engineering Decisions

## Why FastAPI?

Async-native, Pydantic validation is a natural fit for the strict input schemas every guardrail-adjacent endpoint needs, and auto-generated OpenAPI docs give a Razorpay reviewer a working `/docs` page for free. The alternative seriously considered was Flask + marshmallow; FastAPI wins purely on validation being load-bearing here, not incidental.

## Why PostgreSQL?

Real foreign keys, real unique constraints (the idempotency guarantee in `docs/security.md` is a **database** guarantee specifically because Postgres/SQLite both enforce `UNIQUE` at the engine level, not something re-implemented in application code where it could be raced). JSON columns for flexible product specs without needing a NoSQL side-system. SQLite is used as the zero-setup local default so the whole project runs without a Postgres install; the ORM layer (SQLAlchemy) is the actual portability boundary and every model uses dialect-agnostic column types.

## Why Redis (and why it's currently optional)?

Specified for session state, catalog-query caching, and rate limiting. It's included in `docker-compose.yml` and the `USE_REDIS` setting exists, but honestly: this build's rate limiter and session handling currently work fine in-memory for a single-process demo, and wiring Redis in for a feature that doesn't yet need it purely to check a box would be exactly the kind of "complexity for file count" the brief explicitly warns against. It's included and ready; using it is listed as a "Future improvement" rather than faked as done.

## Why tool-calling instead of a free-form agent loop?

A truly open-ended agent loop (model picks from an arbitrary tool list each turn, decides its own sequence) is strictly harder to make safe: every new tool is a new thing a prompt-injected or simply confused model could call in an order nobody designed for. This project uses a **fixed two-step orchestrator** per turn instead (`app/agents/orchestrator.py`): call the AI for language understanding/explanation, call deterministic services for everything else. The AI provider interface has exactly four methods, none of which can touch the database or a payment API. This is a stricter reading of "controlled tool layer" than the brief's suggested tool list implies, and the tradeoff is explicit: less flexible, but there is no code path — not a prompt, not a jailbreak, not a reasoning failure — through which the AI layer can call `create_payment_order` directly, because it structurally has no reference to it.

## Why deterministic pricing?

Because "the AI suggested a price" is not a sentence that should ever be able to be true in the audit log. `calculate_checkout()` takes a cart and a discount percent (itself bounded by a guardrail) and nothing else — there is no parameter through which any actor, AI or otherwise, could inject a number that becomes the charge amount.

## Why explicit payment confirmation?

Because the alternative — inferring "the customer wants to pay" from conversational context — is exactly the kind of judgment call that should never gate an irreversible financial action. `confirm: true` only exists in a request because a real click happened on a real button rendered from real cart data.

## Why idempotency as a DB constraint, not an in-memory cache?

An earlier design used Redis for idempotency tracking. It was rejected for the exact reason `docs/architecture.md` says Redis is never authoritative for financial records: a cache can be evicted, a process can restart, and "was this the same request" is a question whose wrong answer costs real money in production. A `UNIQUE` constraint on `idempotency_keys.key`, checked inside the same transaction as order creation, can't silently disappear.

## A real bug this design decision caught, mid-build

Worth stating plainly rather than glossing over: the first implementation derived the idempotency key from `cart.id` (`f"order_{cart.id}"`). This worked for the "happy path" test but broke under a genuine double-submit: `create_order()` sets `cart.status = "checked_out"`, so a second confirm click's `get_or_create_cart()` call (which only finds carts with `status == "open"`) silently created a **second, empty cart** with a **different id**, and the idempotency key computed from that new id didn't match the first one at all. The "duplicate protection" was checking the wrong invariant — it deduplicated by cart, not by checkout attempt.

The fix: the idempotency key is now generated **client-side**, once, when the checkout confirmation screen is shown, and reused for every retry of that specific submission — independent of what happens to the cart afterward. `POST /api/v1/checkout/confirm` checks this key against the `idempotency_keys` table before touching the cart at all. This is the standard pattern used by Stripe and other payment APIs for exactly this reason, and it's now covered by `tests/test_idempotency_and_retries.py::TestIdempotency` with a test that specifically exercises the client-supplied-key path.

## Why server-side payment verification?

A client reporting "the payment succeeded" is not evidence the payment succeeded — it's evidence a client sent a message that says so. `RazorpayPaymentProvider.verify_payment_signature()` independently recomputes the HMAC from data the client can't forge (the secret half of the signature never leaves the server) and compares in constant time. This is Razorpay's documented verification pattern, not a custom invention.

## Why a mock payment provider exists at all

Two honest reasons, not one: (1) it lets the entire project — including the 105-scenario evaluation suite and all 53 tests — run with zero external accounts or API keys, which matters for anyone trying to actually verify this repository rather than take it on faith; (2) it's the only way to **deterministically** trigger the failure-recovery demo the brief requires. A real payment gateway's test mode can usually be coaxed into a decline with a magic test card number, but "always fail on command, in CI, with a documented reason string" is a property only a mock can guarantee. It is clearly labeled as simulated everywhere it surfaces — see `docs/failure-recovery.md`.

## Why AI is not allowed to directly call payment APIs

Stated elsewhere in this document from several angles, but as a single sentence: the cost of an AI reasoning failure in a chat response is a bad sentence; the cost of an AI reasoning failure with payment-API access is a wrong charge. Those aren't the same risk category, and the architecture treats them differently on purpose rather than applying one "guardrail" wrapper around an otherwise-unrestricted agent.

## A second real bug found during evaluation: audit events lost on guardrail rejection

Discovered while building the pytest suite, not the eval suite: several guardrail-violation code paths logged an audit event via `record_event()` (which only calls `db.flush()`) and then raised an exception. The API layer's exception handler (`app/api/deps.py::guarded()`) converts that straight into an `HTTPException` — it never reaches the endpoint's own `db.commit()`. Since an ORM session rolls back uncommitted work when it closes, **the very audit events meant to prove an unsafe action was blocked were themselves being silently discarded.** Every guardrail-rejection path in `app/services/checkout.py` now calls `db.commit()` immediately after logging the blocked event and before raising. Covered by `tests/test_audit_logging.py::test_blocked_action_produces_guardrail_blocked_event`, and written up in `docs/security.md`.

## A third real bug: cart subtotal read stale immediately after adding an item

`get_cart_snapshot()` originally iterated `cart.items` (a SQLAlchemy relationship). Immediately after `add_to_cart()` called `db.add(item)` + `db.flush()` in the same request, `cart.items` on the in-memory `cart` object hadn't refreshed to include the just-added row — so a customer selecting a product would see a cart subtotal of ₹0 until the *next* request. Fixed by querying `CartItem` directly by `cart_id` instead of relying on the possibly-stale relationship collection. Covered implicitly by every integration test that checks cart state immediately after a mutation (e.g. `tests/test_integration_flows.py::test_chat_search_select_upsell_checkout_payment_success`).

## Why the evaluation numbers include failures

Because a 100% score from a suite the author also wrote is not evidence, it's a tautology. The 105-scenario suite is run for real against the real app and the 5 genuine failures (all one root cause: the mock AI's keyword-based category classifier) are reported rather than quietly removed from the scenario set or reworded until they pass. See `evaluation/README.md` and the README's evaluation section for the full accounting.
