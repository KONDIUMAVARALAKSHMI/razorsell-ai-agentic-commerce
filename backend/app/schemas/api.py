from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str
    user_id: str
    message: str = Field(..., min_length=1, max_length=1000)


class SelectProductRequest(BaseModel):
    session_id: str
    user_id: str
    product_id: str


class UpsellDecisionRequest(BaseModel):
    session_id: str
    user_id: str
    product_id: str
    accept: bool


class CartActionRequest(BaseModel):
    session_id: str
    user_id: str
    product_id: str
    quantity: int = 1


class CheckoutConfirmRequest(BaseModel):
    session_id: str
    user_id: str
    discount_percent: float = 0.0
    confirm: bool
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Client-generated key, stable across retries of the SAME checkout submission "
        "(e.g. generated once when the confirmation screen is shown). Omitting it means each "
        "call is treated as a new checkout attempt.",
    )


class PaymentAttemptRequest(BaseModel):
    order_id: str
    simulated_outcome: Optional[str] = None


class RetryRequest(BaseModel):
    order_id: str


class RazorpayVerifyRequest(BaseModel):
    order_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class GenericResponse(BaseModel):
    ok: bool
    data: Any = None
    error: Optional[str] = None
