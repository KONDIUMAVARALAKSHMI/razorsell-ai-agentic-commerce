# RazorSell AI — Offline Evaluation

## What this is

105 scenarios executed against the **real** FastAPI application (in-process, via `TestClient`) backed by a freshly seeded SQLite database. Nothing here is hard-coded — every number in the report is computed from what the scenarios actually did during that run. Re-run it yourself; you'll get the same result, because the mock AI provider and mock payment provider are both deterministic by design.

## How to run it

```bash
cd razorsell-ai
python3 -m venv .venv && source .venv/bin/activate   # or reuse backend/.venv
pip install -r backend/requirements.txt
python evaluation/runner.py
```

Optional: `--json evaluation/results.json` to dump the full per-scenario breakdown.

## Scenario categories (105 total)

| Category | Count | What it checks |
|---|---|---|
| Shopping (laptop) | 15 | Intent extraction, product grounding, recommendation relevance across varied budget/use-case/priority combinations |
| Shopping (accessory/gaming) | 15 | Same, for non-laptop categories |
| Ambiguous requests | 5 | The system doesn't crash or hallucinate on vague input ("show me your best stuff") |
| Comparison | 10 | `compare_products` returns only real products, silently drops fabricated ids |
| Out-of-stock | 5 | Adding a depleted product is blocked with `INVENTORY_CHECK` |
| Insufficient inventory | 5 | Requesting more units than available is blocked |
| Invalid quantity | 5 | Zero/negative quantities rejected (schema-level or guardrail-level) |
| Payment success | 10 | Full checkout → payment → `SUCCESS` |
| Payment failure → recovery | 10 | Forced failure → retry → forced success, exactly one provider order throughout |
| Duplicate request | 5 | Same idempotency key submitted twice returns the same order |
| Upsell accept/reject | 10 | Both decisions are recorded correctly; absence of a curated upsell is handled gracefully |
| Adversarial / unsafe-action attempts | 10 | Payment without confirmation, hallucinated product id, excessive discount, retry beyond limit, upsell beyond max, negative quantity, retry on a never-failed order — **all must be blocked** |

## Metrics computed

- **Intent accuracy** — for shopping scenarios, whether the category filter the AI's extracted intent produced actually returned products of the expected category.
- **Product grounding accuracy** — every returned `product_id` resolves via `GET /catalog/products/{id}`. Should always be 100% by construction (search only ever queries the real table) — this metric exists to actually verify that construction holds, not to assume it.
- **Recommendation relevance** — the top-ranked result is within the stated budget whenever a cheaper in-category alternative existed.
- **Comparison accuracy** — fabricated ids in a comparison request are dropped, not fabricated back.
- **Checkout completion rate** — pooled across payment success, recovery, and duplicate-request scenarios.
- **Payment success rate**, **failure recovery rate**, **duplicate action prevention rate** — self-explanatory, computed from real HTTP responses.
- **Upsell acceptance rate** — of scenarios where a curated upsell candidate actually existed, how many were accepted (this is a business metric reflecting the scenario mix, not a quality score).
- **Unsafe action block rate** — of the 10 adversarial scenarios, how many were correctly blocked. This is the one number that has zero tolerance for anything less than 100%.

## Latest run (reproducible)

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

Failed scenarios (all the same root cause):

```
[shopping] accessory_19: expected category accessory, got {'laptop'}
[shopping] accessory_24: expected category gaming, got {'laptop'}
[shopping] accessory_25: expected category gaming, got {'accessory'}
[shopping] accessory_27: expected category gaming, got {'accessory'}
[shopping] accessory_29: expected category accessory, got {'laptop'}
```

Each of these is a message like *"laptop charger under 2000 for travel"* or *"cooling pad under 2500 for gaming laptop"*, where `MockAIProvider`'s keyword matcher sees the substring `"laptop"` and classifies the request as category `laptop`, even though the customer is asking for an accessory that merely mentions a laptop as context. This is a real, honest limitation of a zero-dependency, rule-based parser — not a bug in search, pricing, inventory, payments, or any guardrail (all of which scored 100% across every adversarial and financial scenario). `AI_PROVIDER=gemini` would resolve this class of misclassification because a real language model understands "laptop charger" is a request for a charger. It's reported here rather than quietly reworded out of the scenario set, because an evaluation suite that can't surface its own system's real limitations isn't measuring anything.

## Debugging notes from building this suite (kept because they're instructive)

Three real bugs were found and fixed purely by building and iterating on this suite before it produced trustworthy numbers:

1. **A rate limiter throttling the eval harness itself**, which initially made several `duplicate_request` scenarios look like they'd created duplicate orders — they hadn't; the second HTTP call was just getting a `429`, not a `200` with a mismatched order id. Fixed by raising `RATE_LIMIT_PER_MINUTE` for the harness's own process via an environment variable (real customer traffic isn't affected).
2. **SKU collisions across scenario categories** — an `out_of_stock` scenario would permanently zero a product's inventory for the rest of the run, and a handful of `payment_success` / `payment_failure_recovery` / `duplicate_request` / `upsell` scenarios happened to reuse the same SKU, so they failed for a reason that had nothing to do with what they were meant to test. Fixed by giving `out_of_stock` scenarios a dedicated, disjoint SKU pool.
3. **A bug in the metrics computation itself** — `intent_accuracy_percent` was initially computed by filtering to scenarios with `intent_accurate=True` and then computing their overall pass rate (double-filtering), rather than computing what fraction of *all* shopping scenarios had `intent_accurate=True`. This silently inflated the reported number. Fixed by adding a dedicated `_flag_rate()` helper that computes a boolean-flag proportion directly, and the fix is what actually surfaced the 83.33% intent accuracy figure reported above (the old, buggy formula had reported 100%).

All three are also documented in `docs/engineering-decisions.md` and, for the fix that touched production code (#1), in `docs/security.md`.
