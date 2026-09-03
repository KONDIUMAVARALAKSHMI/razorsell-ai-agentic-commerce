from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.payments.base import PaymentProvider
from app.payments.mock_provider import MockPaymentProvider


@lru_cache
def get_payment_provider() -> PaymentProvider:
    settings = get_settings()
    if settings.PAYMENT_PROVIDER == "razorpay":
        from app.payments.razorpay_provider import RazorpayPaymentProvider

        return RazorpayPaymentProvider()
    return MockPaymentProvider()
