from __future__ import annotations

import hashlib
import hmac
from typing import Optional

from app.core.config import get_settings
from app.payments.base import PaymentProvider, ProviderOrder, ProviderPaymentResult

settings = get_settings()


class RazorpayPaymentProvider(PaymentProvider):
    """Thin wrapper around Razorpay's official Python SDK, restricted to
    Test Mode by convention (the key/secret pair used determines test vs
    live - this project must only ever be run with Test Mode credentials).

    Secrets are read once from environment variables via app.core.config and
    are never returned to the frontend or written to logs/audit metadata.
    """

    name = "razorpay"

    def __init__(self) -> None:
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise RuntimeError(
                "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not set. "
                "Set PAYMENT_PROVIDER=mock to run without real Razorpay Test Mode credentials."
            )
        try:
            import razorpay  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'razorpay' package is required for PAYMENT_PROVIDER=razorpay. "
                "Install it with `pip install razorpay` or use PAYMENT_PROVIDER=mock."
            ) from exc
        self._client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    def create_order(self, *, amount_rupees: float, currency: str, receipt: str) -> ProviderOrder:
        amount_paise = round(amount_rupees * 100)
        order = self._client.order.create(
            {
                "amount": amount_paise,
                "currency": currency,
                "receipt": receipt,
                "payment_capture": 1,
            }
        )
        return ProviderOrder(
            provider_order_id=order["id"],
            amount_paise=amount_paise,
            currency=currency,
            status=order.get("status", "created"),
        )

    def capture_or_verify(
        self,
        *,
        provider_order_id: str,
        simulated_outcome: Optional[str] = None,
    ) -> ProviderPaymentResult:
        # Real verification happens via the checkout handoff: the frontend
        # collects razorpay_payment_id / razorpay_order_id / razorpay_signature
        # from Razorpay Checkout and the backend verifies the signature
        # server-side (see app/api/payments.py: /verify). This method covers
        # the server-side signature check path used by that endpoint.
        raise NotImplementedError(
            "Use RazorpayPaymentProvider.verify_payment_signature via the /payments/verify "
            "endpoint - Razorpay Test Mode does not support server-initiated capture in this flow."
        )

    def verify_payment_signature(
        self, *, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str
    ) -> bool:
        body = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected_signature = hmac.new(
            key=settings.RAZORPAY_KEY_SECRET.encode(),
            msg=body.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected_signature, razorpay_signature)

    def verify_webhook_signature(self, *, payload: bytes, signature: str) -> bool:
        if not settings.RAZORPAY_WEBHOOK_SECRET:
            return False
        expected = hmac.new(
            key=settings.RAZORPAY_WEBHOOK_SECRET.encode(),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
