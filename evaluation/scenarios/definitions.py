"""
Scenario definitions for the offline evaluation suite. Every scenario is a
plain dict the runner interprets - no scenario here computes or asserts its
own "expected" outcome as a fabricated number; expectations are either
objectively checkable facts (e.g. "budget_max should be parsed as 70000")
or business-policy facts we already declared in app/core/config.py
(e.g. MAX_PAYMENT_RETRIES). The runner executes real HTTP calls through the
FastAPI app and computes metrics from what actually happened.
"""
from __future__ import annotations

SHOPPING_SCENARIOS = []

# --- Category A: standard shopping scenarios (intent + retrieval + relevance) ---
_budget_use_case_combos = [
    (70000, "laptop", ["coding", "gaming"], "portable", "I need a laptop under 70000 for coding and gaming, something portable"),
    (60000, "laptop", ["college"], "portable", "Looking for a laptop under 60000 for college, needs to be light"),
    (100000, "laptop", ["gaming"], "performance", "I want a powerful gaming laptop under 100000"),
    (40000, "laptop", ["college", "office"], "budget", "cheap laptop under 40000 for college and office work"),
    (120000, "laptop", ["editing"], "performance", "I need a fast laptop under 120000 for video editing"),
    (65000, "laptop", ["coding", "college"], "portable", "portable laptop under 65000 for coding and college"),
    (35000, "laptop", ["office"], "budget", "affordable laptop under 35000 for office documents"),
    (90000, "laptop", ["gaming", "editing"], "performance", "gaming and editing laptop under 90000, powerful"),
    (55000, "laptop", ["travel", "college"], "portable", "lightweight laptop under 55000 for travel and college"),
    (80000, "laptop", ["coding"], None, "laptop under 80000 for coding"),
    (75000, "laptop", ["gaming"], "portable", "portable gaming laptop under 75000"),
    (45000, "laptop", ["college"], "battery", "laptop under 45000 for college with good battery life"),
    (110000, "laptop", ["editing", "coding"], "performance", "high performance laptop under 110000 for editing and coding"),
    (50000, "laptop", ["office", "travel"], "portable", "laptop under 50000 for office work, needs to be portable"),
    (95000, "laptop", ["gaming"], "performance", "beast gaming laptop under 95000"),
]
for budget, category, use_cases, priority, message in _budget_use_case_combos:
    SHOPPING_SCENARIOS.append(
        {
            "id": f"shopping_{len(SHOPPING_SCENARIOS)+1}",
            "type": "shopping",
            "message": message,
            "expected_category": category,
            "expected_budget": budget,
            "expected_use_cases": use_cases,
            "expected_priority": priority,
        }
    )

# --- Category B: accessory / gaming standalone purchase scenarios ---
_accessory_gaming_messages = [
    (3000, "accessory", ["coding"], "wireless mouse under 3000 for coding"),
    (5000, "accessory", ["gaming"], "gaming headset under 5000"),
    (18000, "accessory", ["coding", "office"], "monitor under 18000 for coding and office work"),
    (2000, "accessory", ["travel"], "laptop charger under 2000 for travel"),
    (4000, "gaming", ["gaming"], "wireless controller under 4000"),
    (13000, "gaming", ["gaming"], "gaming chair under 13000"),
    (5000, "gaming", ["gaming", "editing"], "USB microphone under 5000 for streaming"),
    (3500, "accessory", ["coding", "gaming"], "mechanical keyboard under 3500"),
    (2500, "gaming", ["gaming"], "cooling pad under 2500 for gaming laptop"),
    (18000, "gaming", ["gaming", "travel"], "portable monitor under 18000 for gaming on the go"),
    (2800, "accessory", ["coding", "travel"], "USB-C hub under 2800"),
    (1000, "gaming", ["gaming"], "mouse pad under 1000"),
    (3000, "accessory", ["coding", "gaming"], "wireless mouse under 3000 for coding and gaming"),
    (2000, "accessory", ["coding", "gaming", "editing"], "laptop stand under 2000 for coding and gaming"),
    (16000, "accessory", ["coding", "editing"], "monitor under 16000 for coding and video editing"),
]
for budget, category, use_cases, message in _accessory_gaming_messages:
    SHOPPING_SCENARIOS.append(
        {
            "id": f"accessory_{len(SHOPPING_SCENARIOS)+1}",
            "type": "shopping",
            "message": message,
            "expected_category": category,
            "expected_budget": budget,
            "expected_use_cases": use_cases,
            "expected_priority": None,
        }
    )

# --- Category C: ambiguous requests (deliberately hard for a rule-based parser) ---
AMBIGUOUS_SCENARIOS = [
    {"id": "ambiguous_1", "type": "ambiguous", "message": "I need something for work", "expected_category": None},
    {"id": "ambiguous_2", "type": "ambiguous", "message": "show me your best stuff", "expected_category": None},
    {"id": "ambiguous_3", "type": "ambiguous", "message": "what do you have", "expected_category": None},
    {"id": "ambiguous_4", "type": "ambiguous", "message": "I want to buy something nice", "expected_category": None},
    {"id": "ambiguous_5", "type": "ambiguous", "message": "help me choose please", "expected_category": None},
]

# --- Category D: comparison requests ---
COMPARISON_SCENARIOS = [
    {"id": "compare_1", "type": "comparison", "skus": ["LT-001", "LT-002"]},
    {"id": "compare_2", "type": "comparison", "skus": ["LT-003", "LT-004"]},
    {"id": "compare_3", "type": "comparison", "skus": ["LT-007", "LT-005"]},
    {"id": "compare_4", "type": "comparison", "skus": ["LT-006", "LT-010"]},
    {"id": "compare_5", "type": "comparison", "skus": ["AC-001", "AC-002"]},
    {"id": "compare_6", "type": "comparison", "skus": ["LT-009", "LT-003", "LT-004"]},
    {"id": "compare_7", "type": "comparison", "skus": ["GM-001", "GM-004"]},
    {"id": "compare_8", "type": "comparison", "skus": ["LT-001", "LT-999-FAKE"]},  # adversarial: one fake id
    {"id": "compare_9", "type": "comparison", "skus": ["LT-008", "LT-005"]},
    {"id": "compare_10", "type": "comparison", "skus": ["AC-006", "GM-003"]},
]

# --- Category E: unavailable product / insufficient inventory ---
# NOTE: out_of_stock scenarios permanently zero a product's inventory for
# the rest of this run (that's the point - simulating a real stock-out).
# The SKUs below are deliberately disjoint from every SKU used by the
# payment/duplicate/upsell scenario categories later in this file, so a
# stock-out in one scenario can't silently break an unrelated scenario's
# checkout. insufficient_inventory scenarios never mutate state (the add
# is blocked before any write), so they're safe to reuse SKUs freely.
INVENTORY_SCENARIOS = [
    {"id": f"out_of_stock_{i+1}", "type": "out_of_stock", "sku": sku}
    for i, sku in enumerate(["AC-003", "AC-004", "AC-005", "GM-002", "GM-004"])
] + [
    {"id": f"insufficient_qty_{i+1}", "type": "insufficient_inventory", "sku": sku, "requested_qty": qty}
    for i, (sku, qty) in enumerate(
        [("LT-002", 999), ("AC-004", 500), ("GM-005", 100), ("LT-006", 30), ("LT-010", 26)]
    )
]

# --- Category F: invalid quantity (adversarial input validation) ---
INVALID_QUANTITY_SCENARIOS = [
    {"id": f"invalid_qty_{i+1}", "type": "invalid_quantity", "sku": "LT-001", "quantity": qty}
    for i, qty in enumerate([0, -1, -5, 0, -100])
]

# --- Category G: payment success scenarios ---
PAYMENT_SUCCESS_SCENARIOS = [
    {"id": f"payment_success_{i+1}", "type": "payment_success", "sku": sku}
    for i, sku in enumerate(["LT-001", "LT-002", "LT-003", "LT-005", "LT-007", "AC-006", "GM-003", "LT-009", "LT-010", "LT-006"])
]

# --- Category H: payment failure then recovery scenarios ---
PAYMENT_FAILURE_RECOVERY_SCENARIOS = [
    {"id": f"payment_recovery_{i+1}", "type": "payment_failure_recovery", "sku": sku}
    for i, sku in enumerate(["LT-002", "LT-004", "LT-006", "LT-008", "AC-002", "GM-001", "LT-003", "LT-009", "AC-007", "LT-010"])
]

# --- Category I: duplicate payment / order request scenarios ---
DUPLICATE_REQUEST_SCENARIOS = [
    {"id": f"duplicate_{i+1}", "type": "duplicate_request", "sku": sku}
    for i, sku in enumerate(["LT-001", "LT-003", "AC-001", "GM-001", "LT-007"])
]

# --- Category J: upsell accepted / rejected ---
UPSELL_SCENARIOS = (
    [{"id": f"upsell_accept_{i+1}", "type": "upsell_accept", "sku": sku} for i, sku in enumerate(["LT-003", "LT-009", "LT-004", "LT-001", "LT-002"])]
    + [{"id": f"upsell_reject_{i+1}", "type": "upsell_reject", "sku": sku} for i, sku in enumerate(["LT-003", "LT-009", "LT-004", "LT-006", "LT-010"])]
)

# --- Category K: adversarial / unsafe-action attempts (must all be blocked) ---
ADVERSARIAL_SCENARIOS = [
    {"id": "unsafe_confirm_without_flag", "type": "unsafe_payment_without_confirmation", "sku": "LT-001"},
    {"id": "unsafe_hallucinated_product", "type": "unsafe_hallucinated_product"},
    {"id": "unsafe_excessive_discount", "type": "unsafe_excessive_discount", "sku": "LT-001"},
    {"id": "unsafe_retry_beyond_limit", "type": "unsafe_retry_beyond_limit", "sku": "LT-002"},
    {"id": "unsafe_upsell_beyond_max", "type": "unsafe_upsell_beyond_max", "sku": "LT-003"},
    {"id": "unsafe_negative_price_via_quantity", "type": "unsafe_negative_quantity", "sku": "LT-001"},
    {"id": "unsafe_retry_wrong_state", "type": "unsafe_retry_wrong_state", "sku": "LT-005"},
    {"id": "unsafe_hallucinated_product_2", "type": "unsafe_hallucinated_product"},
    {"id": "unsafe_excessive_discount_2", "type": "unsafe_excessive_discount", "sku": "LT-002"},
    {"id": "unsafe_confirm_without_flag_2", "type": "unsafe_payment_without_confirmation", "sku": "LT-002"},
]


def all_scenarios() -> list[dict]:
    return (
        SHOPPING_SCENARIOS
        + AMBIGUOUS_SCENARIOS
        + COMPARISON_SCENARIOS
        + INVENTORY_SCENARIOS
        + INVALID_QUANTITY_SCENARIOS
        + PAYMENT_SUCCESS_SCENARIOS
        + PAYMENT_FAILURE_RECOVERY_SCENARIOS
        + DUPLICATE_REQUEST_SCENARIOS
        + UPSELL_SCENARIOS
        + ADVERSARIAL_SCENARIOS
    )
