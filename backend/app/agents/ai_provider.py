from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ExtractedIntent:
    category: Optional[str] = None
    budget_max: Optional[float] = None
    use_cases: list[str] = field(default_factory=list)
    priority: Optional[str] = None  # e.g. "portable", "performance", "battery"
    raw_summary: str = ""


class AIProvider(ABC):
    """Everything the AI is allowed to do: understand language and explain
    decisions in plain English. It never touches the database, never
    calculates money, and never calls a payment API directly - see
    app/guardrails/policy.py and docs/security.md for the enforcement layer."""

    name: str

    @abstractmethod
    def extract_intent(self, message: str) -> ExtractedIntent:
        ...

    @abstractmethod
    def explain_recommendation(self, *, product_name: str, reasons: list[str]) -> str:
        ...

    @abstractmethod
    def explain_upsell(self, *, product_name: str, primary_product_name: str, reason: str) -> str:
        ...

    @abstractmethod
    def conversational_reply(self, *, context: dict[str, Any]) -> str:
        ...
