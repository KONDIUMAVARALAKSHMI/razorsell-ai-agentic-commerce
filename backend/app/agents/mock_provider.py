from __future__ import annotations

import re
from typing import Any

from app.agents.ai_provider import AIProvider, ExtractedIntent

CATEGORY_KEYWORDS = {
    "laptop": ["laptop", "notebook", "ultrabook"],
    "accessory": ["mouse", "keyboard", "headset", "bag", "charger", "hub", "dock", "monitor", "webcam"],
    "gaming": ["gaming rig", "controller", "console", "gaming chair", "gaming"],
}

USE_CASE_KEYWORDS = {
    "coding": ["coding", "programming", "development", "developer", "code"],
    "gaming": ["gaming", "games", "play games", "fps", "esports"],
    "college": ["college", "university", "school", "student", "class"],
    "editing": ["editing", "video editing", "photo editing", "design", "render"],
    "office": ["office", "excel", "documents", "productivity"],
    "travel": ["travel", "on the go", "commute"],
}

PRIORITY_KEYWORDS = {
    "portable": ["portable", "light", "lightweight", "thin", "travel"],
    "performance": ["fast", "powerful", "performance", "high-end", "beast"],
    "battery": ["battery", "battery life", "all day"],
    "budget": ["cheap", "affordable", "budget", "inexpensive"],
}


def _extract_budget(message: str) -> float | None:
    # Matches things like "70000", "70,000", "70k", "₹70k", "under 70000"
    m = re.search(r"(?:under|below|less than|within)?\s*(?:₹|rs\.?|inr)?\s*([\d,]+)\s*(k)?", message, re.IGNORECASE)
    if not m:
        return None
    number_str = m.group(1).replace(",", "")
    if not number_str.isdigit():
        return None
    value = float(number_str)
    if m.group(2):
        value *= 1000
    # Guard against picking up nonsense small numbers unrelated to budget
    if value < 500:
        return None
    return value


def _match_keywords(message: str, table: dict[str, list[str]]) -> list[str]:
    lowered = message.lower()
    return [key for key, keywords in table.items() if any(kw in lowered for kw in keywords)]


class MockAIProvider(AIProvider):
    """Deterministic, dependency-free AI provider. Used by default
    (AI_PROVIDER=mock) so the whole product - including the evaluation
    suite - runs with zero external API keys. Intent extraction here is
    rule-based rather than a real language model; it is intentionally
    simple and auditable, not a substitute for Gemini's understanding."""

    name = "mock"

    def extract_intent(self, message: str) -> ExtractedIntent:
        categories = _match_keywords(message, CATEGORY_KEYWORDS)
        category = categories[0] if categories else None
        budget = _extract_budget(message)
        use_cases = _match_keywords(message, USE_CASE_KEYWORDS)
        priorities = _match_keywords(message, PRIORITY_KEYWORDS)
        priority = priorities[0] if priorities else None

        parts = []
        if category:
            parts.append(f"a {category}")
        else:
            parts.append("a product")
        if priority:
            parts.append(f"that is {priority}")
        if budget:
            parts.append(f"under ₹{int(budget):,}")
        if use_cases:
            parts.append("for " + ", ".join(use_cases))
        summary = "I understood that you're looking for " + " ".join(parts) + "."

        return ExtractedIntent(
            category=category,
            budget_max=budget,
            use_cases=use_cases,
            priority=priority,
            raw_summary=summary,
        )

    def explain_recommendation(self, *, product_name: str, reasons: list[str]) -> str:
        reason_text = "; ".join(reasons) if reasons else "it is a strong overall match for your request"
        return f"Recommended {product_name} because {reason_text}."

    def explain_upsell(self, *, product_name: str, primary_product_name: str, reason: str) -> str:
        return f"Since you chose {primary_product_name}, {product_name} is worth considering: {reason}"

    def conversational_reply(self, *, context: dict[str, Any]) -> str:
        stage = context.get("stage")
        if stage == "no_results":
            return (
                "I couldn't find a product matching all of those constraints. "
                "Would you like me to relax the budget or category a little?"
            )
        if stage == "checkout_ready":
            return "Here's your order summary. Please review it and confirm to proceed to payment."
        if stage == "payment_blocked":
            return context.get("reason", "That action isn't allowed yet.")
        return "Here's what I found for you."
