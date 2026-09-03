from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderOrder:
    provider_order_id: str
    amount_paise: int
    currency: str
    status: str  # "created"


@dataclass
class ProviderPaymentResult:
    provider_payment_id: Optional[str]
    status: str  # "success" | "failed"
    failure_reason: Optional[str] = None


class PaymentProvider(ABC):
    """Every payment provider (real or mock) implements this interface.
    The AI agent never talks to this layer directly - only the deterministic
    checkout service (app/services/checkout.py) does."""

    name: str

    @abstractmethod
    def create_order(self, *, amount_rupees: float, currency: str, receipt: str) -> ProviderOrder:
        ...

    @abstractmethod
    def capture_or_verify(
        self,
        *,
        provider_order_id: str,
        simulated_outcome: Optional[str] = None,
    ) -> ProviderPaymentResult:
        """Executes/verifies a payment attempt against the provider order.

        `simulated_outcome` is only honored by MockPaymentProvider and lets
        the demo/eval harness deterministically force SUCCESS / FAILURE /
        TIMEOUT / DUPLICATE_REQUEST without touching real payment rails.
        """
        ...

    @abstractmethod
    def verify_webhook_signature(self, *, payload: bytes, signature: str) -> bool:
        ...
