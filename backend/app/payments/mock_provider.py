from __future__ import annotations

import random
import uuid

from app.payments.base import PaymentProvider, ProviderOrder, ProviderPaymentResult

VALID_OUTCOMES = {"SUCCESS", "FAILURE", "TIMEOUT", "DUPLICATE_REQUEST"}


class MockPaymentProvider(PaymentProvider):
    """A LOCAL, DETERMINISTIC simulation of a payment gateway. This is NOT
    Razorpay - it exists so the reliability/failure-recovery story (Section
    10 & 26 of the spec) can be demonstrated and evaluated without real
    payment rails, and so the evaluation suite can run without any API key.

    This must be clearly labeled as simulated everywhere it appears in the
    UI and README - see docs/failure-recovery.md.
    """

    name = "mock"

    def create_order(self, *, amount_rupees: float, currency: str, receipt: str) -> ProviderOrder:
        return ProviderOrder(
            provider_order_id=f"mock_order_{uuid.uuid4().hex[:16]}",
            amount_paise=round(amount_rupees * 100),
            currency=currency,
            status="created",
        )

    def capture_or_verify(
        self,
        *,
        provider_order_id: str,
        simulated_outcome: str | None = None,
    ) -> ProviderPaymentResult:
        outcome = (simulated_outcome or "SUCCESS").upper()
        if outcome not in VALID_OUTCOMES:
            outcome = "SUCCESS"

        if outcome == "SUCCESS":
            return ProviderPaymentResult(
                provider_payment_id=f"mock_pay_{uuid.uuid4().hex[:16]}",
                status="success",
            )
        if outcome == "FAILURE":
            return ProviderPaymentResult(
                provider_payment_id=None,
                status="failed",
                failure_reason="Simulated failure: card declined by issuing bank (demo).",
            )
        if outcome == "TIMEOUT":
            return ProviderPaymentResult(
                provider_payment_id=None,
                status="failed",
                failure_reason="Simulated failure: gateway timeout (demo).",
            )
        if outcome == "DUPLICATE_REQUEST":
            return ProviderPaymentResult(
                provider_payment_id=None,
                status="failed",
                failure_reason="Simulated failure: duplicate request rejected by gateway (demo).",
            )
        # Should be unreachable given the guard above.
        return ProviderPaymentResult(provider_payment_id=None, status="failed", failure_reason="Unknown outcome.")

    def verify_webhook_signature(self, *, payload: bytes, signature: str) -> bool:
        # The mock provider never sends real webhooks; treat any signature
        # equal to "mock-signature" as valid, purely for local testing.
        return signature == "mock-signature"

    @staticmethod
    def random_outcome(failure_rate: float = 0.25) -> str:
        """Helper for the evaluation harness: produces SUCCESS most of the
        time and FAILURE at the given rate, so batch runs can exercise the
        recovery path without every scenario author hand-picking an outcome."""
        return "FAILURE" if random.random() < failure_rate else "SUCCESS"
