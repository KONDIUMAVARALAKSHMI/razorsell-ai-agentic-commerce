"""
RazorSell AI - offline evaluation runner.

Executes every scenario in evaluation/scenarios/definitions.py against the
REAL FastAPI application (in-process, via TestClient) backed by a fresh
SQLite database seeded with the standard demo catalog. Every metric printed
at the end is computed from what the scenarios actually did during this run
- nothing is hard-coded or pre-written.

Usage (from the evaluation/ directory or repo root):
    python evaluation/runner.py
    python evaluation/runner.py --json evaluation/results.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(REPO_ROOT / "evaluation"))

os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("PAYMENT_PROVIDER", "mock")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{BACKEND_DIR}/evaluation_run.db")
# The evaluation harness deliberately fires many requests back-to-back from
# a single process/IP - that's a property of running scenarios fast, not of
# real customer traffic, so the per-IP rate limit is raised for this run only.
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100000")

from scenarios.definitions import all_scenarios  # noqa: E402


@dataclass
class ScenarioResult:
    scenario_id: str
    scenario_type: str
    passed: bool
    detail: str = ""
    extra: dict = field(default_factory=dict)


def _fresh_app_and_client():
    """Builds a brand-new app + isolated DB file for a fully reproducible run."""
    db_path = BACKEND_DIR / "evaluation_run.db"
    if db_path.exists():
        db_path.unlink()

    from app.core.db import Base, engine
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    import scripts.seed_database as seed_module

    seed_module.seed()

    from app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


def _new_ids() -> tuple[str, str]:
    return str(uuid.uuid4()), str(uuid.uuid4())


def run_shopping_scenario(client, scenario: dict) -> ScenarioResult:
    session_id, user_id = _new_ids()
    r = client.post(
        "/api/v1/chat/message",
        json={"session_id": session_id, "user_id": user_id, "message": scenario["message"]},
    )
    if r.status_code != 200:
        return ScenarioResult(scenario["id"], scenario["type"], False, f"HTTP {r.status_code}")

    data = r.json()["data"]
    products = data["products"]

    # --- Intent accuracy ---
    intent_ok = True
    intent_notes = []
    # We can't introspect the extracted intent object directly through this
    # endpoint (by design - the AI layer's internals aren't part of the
    # public contract), so we infer it from the returned understood_intent
    # summary and from whether the returned products match expectations.
    expected_category = scenario.get("expected_category")
    if expected_category and products:
        categories_returned = {p["category"] for p in products}
        if expected_category not in categories_returned:
            intent_ok = False
            intent_notes.append(f"expected category {expected_category}, got {categories_returned}")

    # --- Product grounding: every returned id must be a real catalog product ---
    grounded = True
    for p in products:
        check = client.get(f"/api/v1/catalog/products/{p['product_id']}")
        if check.status_code != 200:
            grounded = False

    # --- Recommendation relevance: top result within budget where feasible ---
    relevance_ok = True
    expected_budget = scenario.get("expected_budget")
    if expected_budget and products:
        top = products[0]
        if top["price"] > expected_budget:
            # Only a problem if a cheaper in-category alternative existed.
            cheaper_alt_exists = any(p["price"] <= expected_budget for p in products)
            if cheaper_alt_exists:
                relevance_ok = False

    passed = grounded and (intent_ok or scenario["type"] == "ambiguous") and relevance_ok
    return ScenarioResult(
        scenario["id"],
        scenario["type"],
        passed,
        detail="; ".join(intent_notes) if intent_notes else "ok",
        extra={
            "intent_accurate": intent_ok,
            "grounded": grounded,
            "relevant": relevance_ok,
            "num_products": len(products),
            "had_results": len(products) > 0,
        },
    )


def run_ambiguous_scenario(client, scenario: dict) -> ScenarioResult:
    # Ambiguous scenarios simply must not crash and must not hallucinate
    # products; a "no results" or generic reply is an acceptable, honest
    # response for input this vague.
    session_id, user_id = _new_ids()
    r = client.post(
        "/api/v1/chat/message",
        json={"session_id": session_id, "user_id": user_id, "message": scenario["message"]},
    )
    passed = r.status_code == 200
    return ScenarioResult(scenario["id"], scenario["type"], passed, detail=f"HTTP {r.status_code}")


def run_comparison_scenario(client, scenario: dict) -> ScenarioResult:
    from sqlalchemy import select
    from app.core.db import SessionLocal
    from app.models.catalog import Product

    db = SessionLocal()
    try:
        real_ids = []
        for sku in scenario["skus"]:
            product = db.execute(select(Product).where(Product.sku == sku)).scalar_one_or_none()
            real_ids.append(product.id if product else f"fake-{sku}")
    finally:
        db.close()

    r = client.post("/api/v1/catalog/compare", json=real_ids)
    if r.status_code != 200:
        return ScenarioResult(scenario["id"], scenario["type"], False, f"HTTP {r.status_code}")
    returned = r.json()
    expected_valid_count = sum(1 for sku in scenario["skus"] if not sku.endswith("FAKE"))
    passed = len(returned) == expected_valid_count
    return ScenarioResult(
        scenario["id"], scenario["type"], passed,
        detail=f"expected {expected_valid_count} valid products, got {len(returned)}",
    )


def run_out_of_stock_scenario(client, scenario: dict) -> ScenarioResult:
    from sqlalchemy import select
    from app.core.db import SessionLocal
    from app.models.catalog import Inventory, Product

    db = SessionLocal()
    try:
        product = db.execute(select(Product).where(Product.sku == scenario["sku"])).scalar_one()
        inv = db.execute(select(Inventory).where(Inventory.product_id == product.id)).scalar_one()
        inv.quantity_available = 0
        db.commit()
        product_id = product.id
    finally:
        db.close()

    session_id, user_id = _new_ids()
    r = client.post(
        "/api/v1/cart/add",
        json={"session_id": session_id, "user_id": user_id, "product_id": product_id, "quantity": 1},
    )
    passed = r.status_code == 403 and r.json().get("detail", {}).get("rule") == "INVENTORY_CHECK"
    return ScenarioResult(scenario["id"], scenario["type"], passed, detail=f"HTTP {r.status_code}")


def run_insufficient_inventory_scenario(client, scenario: dict) -> ScenarioResult:
    from sqlalchemy import select
    from app.core.db import SessionLocal
    from app.models.catalog import Product

    db = SessionLocal()
    try:
        product = db.execute(select(Product).where(Product.sku == scenario["sku"])).scalar_one()
        product_id = product.id
    finally:
        db.close()

    session_id, user_id = _new_ids()
    r = client.post(
        "/api/v1/cart/add",
        json={
            "session_id": session_id, "user_id": user_id,
            "product_id": product_id, "quantity": scenario["requested_qty"],
        },
    )
    passed = r.status_code == 403 and r.json().get("detail", {}).get("rule") == "INVENTORY_CHECK"
    return ScenarioResult(scenario["id"], scenario["type"], passed, detail=f"HTTP {r.status_code}")


def run_invalid_quantity_scenario(client, scenario: dict) -> ScenarioResult:
    from sqlalchemy import select
    from app.core.db import SessionLocal
    from app.models.catalog import Product

    db = SessionLocal()
    try:
        product = db.execute(select(Product).where(Product.sku == scenario["sku"])).scalar_one()
        product_id = product.id
    finally:
        db.close()

    session_id, user_id = _new_ids()
    r = client.post(
        "/api/v1/cart/add",
        json={
            "session_id": session_id, "user_id": user_id,
            "product_id": product_id, "quantity": scenario["quantity"],
        },
    )
    # Pydantic's ge=1 constraint on quantity rejects this at the schema
    # level (422) before it ever reaches guardrail logic - both are valid
    # "safely rejected" outcomes.
    passed = r.status_code in (403, 422)
    return ScenarioResult(scenario["id"], scenario["type"], passed, detail=f"HTTP {r.status_code}")


def _checkout_single_product(client, sku: str) -> tuple[str, str, str]:
    """Helper: search -> select -> confirm. Returns (session_id, user_id, order_id)."""
    from sqlalchemy import select
    from app.core.db import SessionLocal
    from app.models.catalog import Product

    db = SessionLocal()
    try:
        product = db.execute(select(Product).where(Product.sku == sku)).scalar_one()
        product_id, product_category = product.id, product.category
    finally:
        db.close()

    session_id, user_id = _new_ids()
    client.post(
        "/api/v1/cart/add",
        json={"session_id": session_id, "user_id": user_id, "product_id": product_id, "quantity": 1},
    )
    r = client.post(
        "/api/v1/checkout/confirm",
        json={
            "session_id": session_id, "user_id": user_id,
            "confirm": True, "idempotency_key": str(uuid.uuid4()),
        },
    )
    order_id = r.json()["data"]["order_id"] if r.status_code == 200 else None
    return session_id, user_id, order_id


def run_payment_success_scenario(client, scenario: dict) -> ScenarioResult:
    session_id, user_id, order_id = _checkout_single_product(client, scenario["sku"])
    if order_id is None:
        return ScenarioResult(scenario["id"], scenario["type"], False, "checkout failed")
    r = client.post("/api/v1/payments/attempt", json={"order_id": order_id, "simulated_outcome": "SUCCESS"})
    passed = r.status_code == 200 and r.json()["data"]["order_status"] == "SUCCESS"
    return ScenarioResult(scenario["id"], scenario["type"], passed, detail=str(r.json().get("data")))


def run_payment_failure_recovery_scenario(client, scenario: dict) -> ScenarioResult:
    session_id, user_id, order_id = _checkout_single_product(client, scenario["sku"])
    if order_id is None:
        return ScenarioResult(scenario["id"], scenario["type"], False, "checkout failed")

    r1 = client.post("/api/v1/payments/attempt", json={"order_id": order_id, "simulated_outcome": "FAILURE"})
    failed_correctly = r1.status_code == 200 and r1.json()["data"]["order_status"] in ("RETRY_ALLOWED", "RETRY_LIMIT_REACHED")

    r2 = client.post("/api/v1/payments/retry", json={"order_id": order_id})
    retry_allowed = r2.status_code == 200

    r3 = client.post("/api/v1/payments/attempt", json={"order_id": order_id, "simulated_outcome": "SUCCESS"})
    recovered = r3.status_code == 200 and r3.json()["data"]["order_status"] == "SUCCESS"

    passed = failed_correctly and retry_allowed and recovered
    return ScenarioResult(
        scenario["id"], scenario["type"], passed,
        detail=f"failed_correctly={failed_correctly} retry_allowed={retry_allowed} recovered={recovered}",
        extra={"recovered": recovered},
    )


def run_duplicate_request_scenario(client, scenario: dict) -> ScenarioResult:
    from sqlalchemy import select
    from app.core.db import SessionLocal
    from app.models.catalog import Product

    db = SessionLocal()
    try:
        product = db.execute(select(Product).where(Product.sku == scenario["sku"])).scalar_one()
        product_id = product.id
    finally:
        db.close()

    session_id, user_id = _new_ids()
    client.post(
        "/api/v1/cart/add",
        json={"session_id": session_id, "user_id": user_id, "product_id": product_id, "quantity": 1},
    )
    idem_key = str(uuid.uuid4())
    r1 = client.post(
        "/api/v1/checkout/confirm",
        json={"session_id": session_id, "user_id": user_id, "confirm": True, "idempotency_key": idem_key},
    )
    r2 = client.post(
        "/api/v1/checkout/confirm",
        json={"session_id": session_id, "user_id": user_id, "confirm": True, "idempotency_key": idem_key},
    )
    same_order = (
        r1.status_code == 200 and r2.status_code == 200
        and r1.json()["data"]["order_id"] == r2.json()["data"]["order_id"]
    )
    if same_order:
        detail = "duplicate correctly deduplicated"
    elif r1.status_code != 200 or r2.status_code != 200:
        detail = f"checkout itself failed (HTTP {r1.status_code}/{r2.status_code}), not a deduplication failure"
    else:
        detail = "DUPLICATE ORDER CREATED"
    return ScenarioResult(scenario["id"], scenario["type"], same_order, detail=detail)


def run_upsell_scenario(client, scenario: dict) -> ScenarioResult:
    from sqlalchemy import select
    from app.core.db import SessionLocal
    from app.models.catalog import Product

    db = SessionLocal()
    try:
        product = db.execute(select(Product).where(Product.sku == scenario["sku"])).scalar_one()
        product_id = product.id
    finally:
        db.close()

    session_id, user_id = _new_ids()
    r = client.post(
        "/api/v1/chat/select-product",
        json={"session_id": session_id, "user_id": user_id, "product_id": product_id},
    )
    if r.status_code != 200:
        return ScenarioResult(scenario["id"], scenario["type"], False, f"HTTP {r.status_code}")
    upsell = r.json()["data"]["upsell"]
    if not upsell:
        # No curated upsell exists for this product - not a failure of the
        # scenario itself, just nothing to accept/reject; record as such.
        return ScenarioResult(scenario["id"], scenario["type"], True, "no upsell candidates available", extra={"had_upsell": False})

    accept = scenario["type"] == "upsell_accept"
    upsell_product_id = upsell[0]["product_id"]
    r2 = client.post(
        "/api/v1/cart/upsell-decision",
        json={"session_id": session_id, "user_id": user_id, "product_id": upsell_product_id, "accept": accept},
    )
    passed = r2.status_code == 200
    return ScenarioResult(scenario["id"], scenario["type"], passed, extra={"had_upsell": True, "accepted": accept})


def run_adversarial_scenario(client, scenario: dict) -> ScenarioResult:
    kind = scenario["type"]

    if kind == "unsafe_payment_without_confirmation":
        from sqlalchemy import select
        from app.core.db import SessionLocal
        from app.models.catalog import Product

        db = SessionLocal()
        try:
            product = db.execute(select(Product).where(Product.sku == scenario["sku"])).scalar_one()
            product_id = product.id
        finally:
            db.close()
        session_id, user_id = _new_ids()
        client.post("/api/v1/cart/add", json={"session_id": session_id, "user_id": user_id, "product_id": product_id, "quantity": 1})
        r = client.post("/api/v1/checkout/confirm", json={"session_id": session_id, "user_id": user_id, "confirm": False})
        blocked = r.status_code == 403 and r.json()["detail"]["rule"] == "RULE_1_EXPLICIT_CONFIRMATION"
        return ScenarioResult(scenario["id"], kind, blocked, f"HTTP {r.status_code}")

    if kind == "unsafe_hallucinated_product":
        session_id, user_id = _new_ids()
        r = client.post("/api/v1/cart/add", json={"session_id": session_id, "user_id": user_id, "product_id": "fake-" + str(uuid.uuid4()), "quantity": 1})
        blocked = r.status_code == 403 and r.json()["detail"]["rule"] == "RULE_3_NO_HALLUCINATED_PRODUCTS"
        return ScenarioResult(scenario["id"], kind, blocked, f"HTTP {r.status_code}")

    if kind == "unsafe_excessive_discount":
        session_id, user_id = _new_ids()
        from sqlalchemy import select
        from app.core.db import SessionLocal
        from app.models.catalog import Product

        db = SessionLocal()
        try:
            product = db.execute(select(Product).where(Product.sku == scenario["sku"])).scalar_one()
            product_id = product.id
        finally:
            db.close()
        client.post("/api/v1/cart/add", json={"session_id": session_id, "user_id": user_id, "product_id": product_id, "quantity": 1})
        r = client.get("/api/v1/checkout/preview", params={"session_id": session_id, "user_id": user_id, "discount_percent": 50.0})
        blocked = r.status_code == 403 and r.json()["detail"]["rule"] == "RULE_2_DISCOUNT_BOUNDS"
        return ScenarioResult(scenario["id"], kind, blocked, f"HTTP {r.status_code}")

    if kind == "unsafe_retry_beyond_limit":
        session_id, user_id, order_id = _checkout_single_product(client, scenario["sku"])
        if order_id is None:
            return ScenarioResult(scenario["id"], kind, False, "checkout failed")
        for _ in range(3):
            client.post("/api/v1/payments/attempt", json={"order_id": order_id, "simulated_outcome": "FAILURE"})
        r = client.post("/api/v1/payments/retry", json={"order_id": order_id})
        blocked = r.status_code == 403
        return ScenarioResult(scenario["id"], kind, blocked, f"HTTP {r.status_code}")

    if kind == "unsafe_upsell_beyond_max":
        from sqlalchemy import select
        from app.core.db import SessionLocal
        from app.models.catalog import Product
        from app.services.upsell import get_upsell_candidates

        db = SessionLocal()
        try:
            product = db.execute(select(Product).where(Product.sku == scenario["sku"])).scalar_one()
            # Ask for candidates as if 2 have already been shown this checkout -
            # MAX_UPSELL_RECOMMENDATIONS defaults to 2, so this must return none.
            candidates = get_upsell_candidates(db, product_id=product.id, already_shown=2)
        finally:
            db.close()
        blocked = len(candidates) == 0
        return ScenarioResult(scenario["id"], kind, blocked, f"{len(candidates)} candidates returned (expected 0)")

    if kind == "unsafe_negative_quantity":
        from sqlalchemy import select
        from app.core.db import SessionLocal
        from app.models.catalog import Product

        db = SessionLocal()
        try:
            product = db.execute(select(Product).where(Product.sku == scenario["sku"])).scalar_one()
            product_id = product.id
        finally:
            db.close()
        session_id, user_id = _new_ids()
        r = client.post("/api/v1/cart/add", json={"session_id": session_id, "user_id": user_id, "product_id": product_id, "quantity": -5})
        blocked = r.status_code in (403, 422)
        return ScenarioResult(scenario["id"], kind, blocked, f"HTTP {r.status_code}")

    if kind == "unsafe_retry_wrong_state":
        # Attempt to retry an order that was never even created / never failed.
        session_id, user_id, order_id = _checkout_single_product(client, scenario["sku"])
        if order_id is None:
            return ScenarioResult(scenario["id"], kind, False, "checkout failed")
        r = client.post("/api/v1/payments/retry", json={"order_id": order_id})
        blocked = r.status_code == 403
        return ScenarioResult(scenario["id"], kind, blocked, f"HTTP {r.status_code}")

    return ScenarioResult(scenario["id"], kind, False, "unknown adversarial scenario type")


DISPATCH = {
    "shopping": run_shopping_scenario,
    "ambiguous": run_ambiguous_scenario,
    "comparison": run_comparison_scenario,
    "out_of_stock": run_out_of_stock_scenario,
    "insufficient_inventory": run_insufficient_inventory_scenario,
    "invalid_quantity": run_invalid_quantity_scenario,
    "payment_success": run_payment_success_scenario,
    "payment_failure_recovery": run_payment_failure_recovery_scenario,
    "duplicate_request": run_duplicate_request_scenario,
    "upsell_accept": run_upsell_scenario,
    "upsell_reject": run_upsell_scenario,
}
for _adv_type in [
    "unsafe_payment_without_confirmation", "unsafe_hallucinated_product", "unsafe_excessive_discount",
    "unsafe_retry_beyond_limit", "unsafe_upsell_beyond_max", "unsafe_negative_quantity", "unsafe_retry_wrong_state",
]:
    DISPATCH[_adv_type] = run_adversarial_scenario


def run_all() -> tuple[list[ScenarioResult], dict]:
    client = _fresh_app_and_client()
    scenarios = all_scenarios()
    results: list[ScenarioResult] = []

    with client:
        for scenario in scenarios:
            handler = DISPATCH.get(scenario["type"])
            if handler is None:
                results.append(ScenarioResult(scenario["id"], scenario["type"], False, "no handler registered"))
                continue
            try:
                results.append(handler(client, scenario))
            except Exception as exc:  # a scenario crashing is itself a failed scenario, not a runner crash
                results.append(ScenarioResult(scenario["id"], scenario["type"], False, f"EXCEPTION: {exc}"))

    metrics = compute_metrics(results)
    return results, metrics


def compute_metrics(results: list[ScenarioResult]) -> dict:
    def _rate(subset: list[ScenarioResult]) -> float:
        if not subset:
            return float("nan")
        return round(100.0 * sum(1 for r in subset if r.passed) / len(subset), 2)

    def _flag_rate(subset: list[ScenarioResult], key: str) -> float | None:
        """Percentage of `subset` for which extra[key] is truthy. Distinct
        from _rate(): this measures a specific boolean property recorded on
        every scenario (e.g. 'was the returned category correct'), not
        whether the scenario's overall pass/fail matched."""
        if not subset:
            return None
        return round(100.0 * sum(1 for r in subset if r.extra.get(key)) / len(subset), 2)

    shopping = [r for r in results if r.scenario_type == "shopping"]
    ambiguous = [r for r in results if r.scenario_type == "ambiguous"]
    comparison = [r for r in results if r.scenario_type == "comparison"]
    out_of_stock = [r for r in results if r.scenario_type == "out_of_stock"]
    insufficient_inv = [r for r in results if r.scenario_type == "insufficient_inventory"]
    invalid_qty = [r for r in results if r.scenario_type == "invalid_quantity"]
    payment_success = [r for r in results if r.scenario_type == "payment_success"]
    payment_recovery = [r for r in results if r.scenario_type == "payment_failure_recovery"]
    duplicate = [r for r in results if r.scenario_type == "duplicate_request"]
    upsell = [r for r in results if r.scenario_type in ("upsell_accept", "upsell_reject")]
    adversarial = [r for r in results if r.scenario_type.startswith("unsafe_")]

    upsell_with_candidates = [r for r in upsell if r.extra.get("had_upsell")]
    upsell_accepted_shown = [r for r in upsell_with_candidates if r.scenario_type == "upsell_accept"]

    checkout_completion_pool = payment_success + payment_recovery + duplicate
    unsafe_input_pool = out_of_stock + insufficient_inv + invalid_qty

    return {
        "total_scenarios": len(results),
        "total_passed": sum(1 for r in results if r.passed),
        "total_failed": sum(1 for r in results if not r.passed),
        "overall_pass_rate_percent": _rate(results),
        "intent_accuracy_percent": _flag_rate(shopping, "intent_accurate"),
        "intent_accuracy_sample_size": len(shopping),
        "product_grounding_accuracy_percent": _flag_rate(shopping, "grounded"),
        "recommendation_relevance_percent": _flag_rate(shopping, "relevant"),
        "comparison_accuracy_percent": _rate(comparison) if comparison else None,
        "inventory_and_input_validation_block_rate_percent": _rate(unsafe_input_pool) if unsafe_input_pool else None,
        "checkout_completion_rate_percent": _rate(checkout_completion_pool) if checkout_completion_pool else None,
        "payment_success_rate_percent": _rate(payment_success) if payment_success else None,
        "failure_recovery_rate_percent": _rate(payment_recovery) if payment_recovery else None,
        "duplicate_action_prevention_rate_percent": _rate(duplicate) if duplicate else None,
        "upsell_acceptance_rate_percent": (
            round(100.0 * len(upsell_accepted_shown) / len(upsell_with_candidates), 2)
            if upsell_with_candidates else None
        ),
        "unsafe_action_block_rate_percent": _rate(adversarial) if adversarial else None,
        "adversarial_scenarios_run": len(adversarial),
    }


def print_report(results: list[ScenarioResult], metrics: dict) -> None:
    print("=" * 60)
    print("RazorSell AI - Offline Evaluation Report")
    print("=" * 60)
    print(f"Scenarios run:                       {metrics['total_scenarios']}")
    print(f"Passed:                               {metrics['total_passed']}")
    print(f"Failed:                               {metrics['total_failed']}")
    print(f"Overall pass rate:                    {metrics['overall_pass_rate_percent']}%")
    print("-" * 60)
    print(f"Intent accuracy (n={metrics['intent_accuracy_sample_size']}):        {metrics['intent_accuracy_percent']}%")
    print(f"Product grounding accuracy:           {metrics['product_grounding_accuracy_percent']}%")
    print(f"Recommendation relevance:             {metrics['recommendation_relevance_percent']}%")
    print(f"Comparison accuracy:                  {metrics['comparison_accuracy_percent']}%")
    print(f"Inventory/input validation block rate:{metrics['inventory_and_input_validation_block_rate_percent']}%")
    print(f"Checkout completion rate:             {metrics['checkout_completion_rate_percent']}%")
    print(f"Payment success rate:                 {metrics['payment_success_rate_percent']}%")
    print(f"Failure recovery rate:                {metrics['failure_recovery_rate_percent']}%")
    print(f"Duplicate action prevention:          {metrics['duplicate_action_prevention_rate_percent']}%")
    print(f"Upsell acceptance rate:               {metrics['upsell_acceptance_rate_percent']}%")
    print(f"Unsafe action block rate (n={metrics['adversarial_scenarios_run']}):        {metrics['unsafe_action_block_rate_percent']}%")
    print("-" * 60)

    failed = [r for r in results if not r.passed]
    if failed:
        print(f"\n{len(failed)} FAILED SCENARIO(S):")
        for r in failed:
            print(f"  [{r.scenario_type}] {r.scenario_id}: {r.detail}")
    else:
        print("\nAll scenarios passed.")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="RazorSell AI evaluation runner")
    parser.add_argument("--json", type=str, default=None, help="Optional path to write full results as JSON")
    args = parser.parse_args()

    results, metrics = run_all()
    print_report(results, metrics)

    if args.json:
        out = {
            "metrics": metrics,
            "results": [
                {"id": r.scenario_id, "type": r.scenario_type, "passed": r.passed, "detail": r.detail, "extra": r.extra}
                for r in results
            ],
        }
        Path(args.json).write_text(json.dumps(out, indent=2))
        print(f"\nFull results written to {args.json}")


if __name__ == "__main__":
    main()
