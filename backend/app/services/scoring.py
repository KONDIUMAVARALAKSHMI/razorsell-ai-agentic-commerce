"""
Deterministic recommendation scoring. The AI explains WHY a product was
recommended; it never decides WHICH products are candidates or their rank -
that's this module's job, so the ranking is reproducible and cannot hallucinate.

score = relevance_score + budget_score + use_case_score + portability_score + inventory_score
"""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.ai_provider import ExtractedIntent
from app.models.catalog import Product


@dataclass
class ScoredProduct:
    product: Product
    score: float
    reasons: list[str]


def score_product(product: Product, intent: ExtractedIntent, quantity_available: int) -> ScoredProduct:
    reasons: list[str] = []
    score = 0.0

    # Category relevance (0-30)
    relevance_score = 0.0
    if intent.category and product.category == intent.category:
        relevance_score = 30.0
        reasons.append(f"matches the {intent.category} category you asked for")
    elif intent.category is None:
        relevance_score = 15.0  # neutral if no category was expressed
    score += relevance_score

    # Budget fit (0-25): full score if comfortably under budget, tapering to 0 if over
    budget_score = 12.5  # neutral default
    if intent.budget_max:
        if product.price <= intent.budget_max:
            headroom = (intent.budget_max - product.price) / intent.budget_max
            budget_score = 15.0 + min(headroom, 1.0) * 10.0
            reasons.append(f"fits within your ₹{int(intent.budget_max):,} budget at ₹{int(product.price):,}")
        else:
            over_by = (product.price - intent.budget_max) / intent.budget_max
            budget_score = max(0.0, 15.0 - over_by * 30.0)
    score += budget_score

    # Use-case fit (0-25): based on tags overlapping requested use cases
    use_case_score = 0.0
    if intent.use_cases:
        product_tags = {t.lower() for t in (product.tags or [])}
        matched = [uc for uc in intent.use_cases if uc.lower() in product_tags]
        if matched:
            use_case_score = min(len(matched), 3) * 8.0
            reasons.append("supports " + ", ".join(matched))
    else:
        use_case_score = 10.0
    score += use_case_score

    # Portability priority (0-10)
    portability_score = 0.0
    if intent.priority == "portable":
        portability_score = product.portability_score * 10.0
        if product.portability_score >= 0.7:
            reasons.append("is lightweight and easy to carry")
    elif intent.priority == "performance":
        portability_score = product.performance_score * 10.0
        if product.performance_score >= 0.7:
            reasons.append("has strong performance for demanding tasks")
    else:
        portability_score = 5.0
    score += portability_score

    # Inventory (0-10): in-stock products are preferred; out-of-stock scored to 0
    inventory_score = 10.0 if quantity_available > 0 else 0.0
    if quantity_available <= 0:
        reasons.append("is currently out of stock")
    score += inventory_score

    return ScoredProduct(product=product, score=round(score, 2), reasons=reasons)


def rank_products(products_with_stock: list[tuple[Product, int]], intent: ExtractedIntent) -> list[ScoredProduct]:
    scored = [score_product(p, intent, qty) for p, qty in products_with_stock]
    return sorted(scored, key=lambda s: s.score, reverse=True)
