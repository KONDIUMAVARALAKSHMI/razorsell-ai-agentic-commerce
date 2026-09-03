from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SearchProductsInput(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


class ProductIdInput(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=36)


class CompareProductsInput(BaseModel):
    product_ids: list[str] = Field(..., min_length=2, max_length=5)


class AddToCartInput(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=10)
    added_via: str = Field(default="user")

    @field_validator("added_via")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        if v not in {"user", "upsell_accept"}:
            raise ValueError("added_via must be 'user' or 'upsell_accept'")
        return v


class UpdateQuantityInput(BaseModel):
    product_id: str
    quantity: int = Field(..., ge=0, le=10)


class CalculateCheckoutInput(BaseModel):
    discount_percent: float = Field(default=0.0, ge=0.0, le=100.0)


class ConfirmPaymentInput(BaseModel):
    discount_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    confirm: bool = Field(..., description="Must be true - this is the explicit user confirmation gate.")


class PaymentRetryInput(BaseModel):
    order_id: str


class SimulatePaymentInput(BaseModel):
    order_id: str
    outcome: str = Field(default="SUCCESS")

    @field_validator("outcome")
    @classmethod
    def _valid_outcome(cls, v: str) -> str:
        allowed = {"SUCCESS", "FAILURE", "TIMEOUT", "DUPLICATE_REQUEST"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"outcome must be one of {allowed}")
        return v_upper
