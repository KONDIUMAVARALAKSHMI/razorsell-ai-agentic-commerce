"""
Deterministic guardrails. These functions are the enforcement point for the
safety rules documented in docs/security.md (Rules 1-9). They are called
from app/services/*, never from the AI layer, and every BLOCKED decision
must be paired with an audit event by the caller.

Design principle: fail closed. If a guardrail cannot positively confirm an
action is safe, it blocks the action rather than allowing it.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings

settings = get_settings()


class GuardrailViolation(Exception):
    """Raised when a requested action violates a hard safety rule. Callers
    must catch this, record a GUARDRAIL_BLOCKED audit event, and return a
    safe, explanatory response to the user - never a raw stack trace."""

    def __init__(self, rule: str, message: str):
        self.rule = rule
        self.message = message
        super().__init__(f"[{rule}] {message}")


@dataclass
class GuardrailContext:
    session_id: str
    upsell_count_this_checkout: int = 0
    payment_confirmed: bool = False
    retry_count: int = 0


def enforce_max_upsell(ctx: GuardrailContext) -> None:
    """Rule 4: AI cannot exceed maximum upsell recommendations."""
    if ctx.upsell_count_this_checkout >= settings.MAX_UPSELL_RECOMMENDATIONS:
        raise GuardrailViolation(
            "RULE_4_MAX_UPSELL",
            f"Maximum of {settings.MAX_UPSELL_RECOMMENDATIONS} upsell recommendations already shown this checkout.",
        )


def enforce_payment_requires_confirmation(ctx: GuardrailContext) -> None:
    """Rule 1: AI cannot create a payment order without explicit user confirmation."""
    if not ctx.payment_confirmed:
        raise GuardrailViolation(
            "RULE_1_EXPLICIT_CONFIRMATION",
            "Payment cannot be initiated until the customer explicitly confirms the final order amount.",
        )


def enforce_retry_limit(ctx: GuardrailContext) -> None:
    """Rule 5: AI cannot retry payments indefinitely."""
    if ctx.retry_count >= settings.MAX_PAYMENT_RETRIES:
        raise GuardrailViolation(
            "RULE_5_RETRY_LIMIT",
            f"Maximum retry count of {settings.MAX_PAYMENT_RETRIES} has been reached. Manual action is required.",
        )


def enforce_discount_within_bounds(discount_percent: float) -> None:
    """Rule 2 (extension): discounts are merchant-configured, never
    AI-invented, and can never exceed the configured ceiling."""
    if discount_percent < 0 or discount_percent > settings.MAX_DISCOUNT_PERCENT:
        raise GuardrailViolation(
            "RULE_2_DISCOUNT_BOUNDS",
            f"Discount of {discount_percent}% is outside the allowed range (0-{settings.MAX_DISCOUNT_PERCENT}%).",
        )


def enforce_product_exists(product) -> None:
    """Rule 3: AI cannot invent catalog products. `product` must be a
    row fetched from the database by the caller; None means it doesn't exist."""
    if product is None:
        raise GuardrailViolation("RULE_3_NO_HALLUCINATED_PRODUCTS", "Referenced product does not exist in the catalog.")


def enforce_inventory_available(quantity_available: int, requested_quantity: int) -> None:
    if requested_quantity > quantity_available:
        raise GuardrailViolation(
            "INVENTORY_CHECK",
            f"Only {quantity_available} unit(s) available, {requested_quantity} requested.",
        )
