# RazorSell AI

**An AI Merchant Sales &amp; Agentic Checkout Platform**
Built for the Razorpay AI Buildathon 2026 — Track 01: AI Growth &amp; Agentic Commerce

> Razorpay **Test Mode** only. No real money moves anywhere in this project.

---

## 1. The problem

Customers browsing an electronics store have to already know what they want: which laptop, which spec tier, which accessories are actually compatible. That friction costs merchants conversions and basket size. RazorSell AI turns that browsing session into a conversation: a customer describes a budget and a use case, the assistant searches the real catalog, explains its recommendations, offers one or two genuinely relevant add-ons, and hands off to a deterministic, auditable checkout.

The interesting engineering problem isn't "can an LLM recommend a laptop" — it's **how much of a checkout flow can you hand to an AI agent before you've built something that can accidentally move money it shouldn't.** This project's actual thesis is:

> Let AI improve discovery and explanation. Let deterministic code own every action that touches price, inventory, or payment.

## 2. Why this matters / AI judgment

Every part of this system that touches money is boring on purpose:

- The AI **never** calls a payment API. It can only ask the backend to run `calculate_checkout()`, and that function recomputes the total from the live database — it has no parameter for a price the AI suggests.
- The AI **never** decides if a payment is allowed to fire. `create_order()` hard-fails unless the frontend passed `confirm: true`, and that flag only exists because a human clicked **"Confirm & Proceed to Payment"**.
- The AI **never** picks upsell candidates freely. Every recommendation must trace back to a merchant-curated `ProductRelation` row; the AI's only job is to explain *why* a candidate the deterministic layer already selected is relevant.

Where AI is used, it earns its place: turning "laptop under 70k for coding and gaming, portable" into a structured intent, and turning a scored product list into a one-sentence, grounded explanation a human would actually want to read. Where AI is deliberately **not** used: pricing, inventory, discount calculation, payment execution, retry policy, and upsell selection. See [`docs/architecture.md`](docs/architecture.md) for the full breakdown and [`docs/security.md`](docs/security.md) for the nine guardrail rules that enforce this split in code, not just in prose.

## 3. Product overview

- **Customer chat** — natural-language shopping assistant, grounded product cards, side-by-side comparison, cart.
- **Bounded checkout** — server-priced order summary, explicit confirmation gate, Razorpay Test Mode (or a clearly-labeled local mock) payment, retry with a hard limit, full audit trail.
- **Merchant dashboard** — revenue/agent/reliability metrics computed live from the database, an order explorer, a ledger-style audit trail with filters, and a failure center surfacing every blocked or failed action.

## 4. Key features

| Area | What's implemented |
|---|---|
| Intent understanding | Rule-based mock parser (default, zero dependencies) or Gemini (optional), behind a common interface |
| Product discovery | Deterministic multi-factor scorer (category, budget, use-case, portability/performance, inventory) |
| Upsell/cross-sell | Merchant-curated relations only, capped at 2 per checkout, always shown with price and an explicit accept/reject |
| Cart & pricing | Server-side only; the client can never set a price |
| Checkout | Explicit confirmation gate, application-level idempotency (unique DB constraint), full state machine |
| Payments | Provider abstraction — `MockPaymentProvider` (deterministic SUCCESS/FAILURE/TIMEOUT/DUPLICATE simulation) and `RazorpayPaymentProvider` (real Test Mode + signature verification) |
| Retries | Hard-capped at 3, audited whether allowed or blocked |
| Audit trail | Single write path (`app/audit/service.py`), 19 closed event types, queryable by session/order/actor/status |
| Evaluation | 105 scenarios executed against the real app, metrics computed from what actually happened |
| Tests | 53 pytest tests: cart math, guardrails, idempotency, retries, audit coverage, AI-safety/hallucination resistance, full integration flows |

## 5. Architecture

```
React Client → FastAPI API → AI Agent / Guardrails / Audit Layer → Controlled Tools → PostgreSQL + Redis → Razorpay Test Mode
```

Full diagram and the AI/deterministic split: [`docs/architecture.md`](docs/architecture.md).

## 6. Safety model

Nine explicit rules, enforced in `app/guardrails/policy.py`, every violation audited: [`docs/security.md`](docs/security.md).

## 7. Payment flow & failure recovery

Order state machine, the mandatory failure demo, and how duplicate requests are actually prevented: [`docs/failure-recovery.md`](docs/failure-recovery.md).

## 8. Evaluation methodology & results

Full methodology in [`evaluation/README.md`](evaluation/README.md). The headline run (reproducible — see below):

```
Scenarios run:                        105
Passed:                                100
Failed:                                  5
Overall pass rate:                   95.24%
------------------------------------------------------------
Intent accuracy (n=30):               83.33%
Product grounding accuracy:          100.0%
Recommendation relevance:            100.0%
Comparison accuracy:                 100.0%
Inventory/input validation block rate:100.0%
Checkout completion rate:            100.0%
Payment success rate:                100.0%
Failure recovery rate:               100.0%
Duplicate action prevention:         100.0%
Upsell acceptance rate:               44.44%
Unsafe action block rate (n=10):     100.0%
```

**Every one of the 5 failures is the same root cause**: the deterministic, dependency-free `MockAIProvider` classifies "laptop charger" or "cooling pad for gaming laptop" as category `laptop` because it does keyword matching, not real language understanding. It is **not** a failure of pricing, inventory, payments, idempotency, or any guardrail — those all scored 100%. Switching `AI_PROVIDER=gemini` would resolve this class of error entirely; the mock exists specifically so the whole product runs with zero API keys. This is reported honestly rather than removed from the scenario set — see `evaluation/results.json` for the full per-scenario breakdown, and [`evaluation/README.md`](evaluation/README.md) for how to reproduce this exact run.

## 9. Screenshots

No static screenshots are included in this repository — the fastest way to see the real UI is to run it locally (5 minutes, see below) or follow [`docs/demo-script.md`](docs/demo-script.md). `docs/screenshots/` is left as a placeholder for anyone packaging this for submission to drop in captures of the running app.

## 10. Setup instructions

### Option A — Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up --build
```

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:5173

The backend container runs migrations and seeds the catalog automatically on startup.

> **Verification note:** this repository was developed in a sandboxed environment with no Docker daemon available, so `docker compose up --build` could not be executed here. The Dockerfiles and compose file were verified by careful inspection (valid YAML, correct env var names matching `app/core/config.py`, `psycopg2-binary` present for Postgres, healthcheck-gated startup order) and every command they run (`alembic upgrade head`, `python scripts/seed_database.py`, `uvicorn ...`) was independently verified working against SQLite in this same environment. Please run the commands above yourself and open an issue if anything doesn't come up cleanly.

### Option B — Run locally without Docker

**Backend:**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # defaults to SQLite + mock providers, no keys needed
alembic upgrade head
python scripts/seed_database.py
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env      # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

Visit http://localhost:5173.

## 11. Environment variables

See [`.env.example`](.env.example) (root, backend) and [`frontend/.env.example`](frontend/.env.example). Every variable has a safe default — the project runs with **zero API keys** in mock mode.

## 12. Razorpay Test Mode setup

1. Create a free Razorpay account, switch to **Test Mode**, and copy the Test Key ID/Secret from Settings → API Keys.
2. Set `PAYMENT_PROVIDER=razorpay`, `RAZORPAY_KEY_ID=...`, `RAZORPAY_KEY_SECRET=...`.
3. The frontend's Razorpay Checkout handoff posts to `/api/v1/payments/verify`, which does server-side HMAC signature verification (`app/payments/razorpay_provider.py`) — never trust a client-reported payment status.
4. Never use live keys. This project has no code path that expects them and no safeguard against someone supplying them anyway — that is a deliberate scope decision, documented in `docs/security.md`.

## 13. Demo credentials

Merchant dashboard: username `merchant`, password `demo-password` (change via `MERCHANT_DASHBOARD_USERNAME` / `MERCHANT_DASHBOARD_PASSWORD`).

## 14. Demo walkthrough

See [`docs/demo-script.md`](docs/demo-script.md) for the full 5-minute script matching the required story beats (search → recommend → cross-sell → cart → confirm → Razorpay Test order → forced failure → recovery → audit trail → metrics).

## 15. Testing

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

53 tests, last verified run: **53 passed**. Covers cart calculations, discount/guardrail rules, idempotency, retry limits, audit-event coverage (including that blocked actions are still audited), AI-safety adversarial cases (hallucinated products, unauthorized discounts, payment-without-confirmation, unrelated upsells, out-of-stock recommendations), and full integration flows through the real FastAPI app.

## 16. Known limitations

- **Single merchant, single currency (INR).** Multi-tenant scoping was out of scope for this build; `Merchant` exists as a row but nothing is scoped by it yet.
- **Merchant auth is demo-grade.** Fixed credentials from environment variables + an HMAC-signed opaque token, not a real user/session/permissions system. Fine for a hackathon reviewer, not for production.
- **`MockAIProvider` is a keyword parser, not language understanding.** See the evaluation results above — this is the source of 100% of the eval suite's failures. `AI_PROVIDER=gemini` exists specifically to remove this limitation.
- **Postgres and Docker Compose were verified by inspection, not live execution**, for the reason stated in section 10. SQLite was exercised extensively (migrations, seed, full API surface, 53 tests, 105-scenario eval) in this environment.
- **Rate limiting is in-memory, per-process.** Fine for a single-container demo; a real multi-instance deployment needs it backed by Redis (the `USE_REDIS` setting exists but this specific piece isn't wired to it yet).
- **No email/SMS receipts, no webhooks consumed** beyond the signature-verification helper — the Razorpay webhook secret is read and a verifier exists, but no endpoint currently receives webhook POSTs (Test Mode payments here are verified via the client-side checkout handoff, which is a supported Razorpay integration pattern, not the only one).

## 17. Future improvements

- Wire `USE_REDIS` through to the rate limiter and to catalog-query caching.
- Multi-merchant scoping.
- A real webhook receiver as a second, defense-in-depth path to payment confirmation alongside the signature-verified client handoff.
- Replace the demo merchant auth with a real identity provider.

## 18. Engineering decisions

Every non-obvious choice (why FastAPI, why Postgres, why tool-calling instead of a free-form agent loop, why the AI is architecturally barred from payment APIs, why idempotency is a unique DB constraint and not just "best effort") is written up in [`docs/engineering-decisions.md`](docs/engineering-decisions.md).

---

## Project structure

```
razorsell-ai/
├── frontend/            React + TypeScript + Vite + Tailwind
├── backend/
│   ├── app/
│   │   ├── api/          FastAPI routers
│   │   ├── agents/       AI provider abstraction + orchestrator
│   │   ├── payments/     Payment provider abstraction (mock + Razorpay)
│   │   ├── guardrails/   The 9 safety rules
│   │   ├── audit/        Single audit-write path
│   │   ├── services/     Deterministic business logic (cart, checkout, catalog, upsell, scoring)
│   │   ├── models/       SQLAlchemy models
│   │   └── schemas/      Pydantic request/response models
│   ├── tests/            53 pytest tests
│   ├── alembic/          Migrations
│   └── scripts/          seed_database.py
├── evaluation/
│   ├── scenarios/        105 scenario definitions
│   ├── runner.py         Executes scenarios against the real app, computes real metrics
│   └── README.md
├── docs/                 architecture, security, failure-recovery, engineering-decisions, demo-script
├── docker-compose.yml
└── .env.example
```
