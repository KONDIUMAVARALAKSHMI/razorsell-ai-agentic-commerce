from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Order state machine (deterministic, enforced in app/services/checkout.py):
#   CREATED -> PAYMENT_PENDING -> SUCCESS
#   PAYMENT_PENDING -> FAILED -> RETRY_ALLOWED -> PAYMENT_PENDING
#   FAILED -> RETRY_LIMIT_REACHED -> MANUAL_ACTION_REQUIRED
ORDER_STATES = (
    "CREATED",
    "PAYMENT_PENDING",
    "SUCCESS",
    "FAILED",
    "RETRY_ALLOWED",
    "RETRY_LIMIT_REACHED",
    "MANUAL_ACTION_REQUIRED",
    "CANCELLED",
)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    cart_id: Mapped[str] = mapped_column(String(36), ForeignKey("carts.id"))

    subtotal: Mapped[float] = mapped_column(Float)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float)  # in INR rupees (paise conversion happens at gateway edge)

    status: Mapped[str] = mapped_column(String(30), default="CREATED")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)

    razorpay_order_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payment_attempts: Mapped[list["PaymentAttempt"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"))
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)  # snapshot of product.price at confirmation time
    line_total: Mapped[float] = mapped_column(Float)

    order: Mapped["Order"] = relationship(back_populates="items")


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"))
    attempt_number: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(20))  # razorpay | mock
    provider_payment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    simulated_outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)  # for mock provider only
    status: Mapped[str] = mapped_column(String(20))  # PENDING | SUCCESS | FAILED
    failure_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    order: Mapped["Order"] = relationship(back_populates="payment_attempts")


class IdempotencyKey(Base):
    """Application-level idempotency ledger. A unique DB constraint on `key`
    guarantees that concurrent duplicate requests can create at most one
    order, even if Redis is unavailable."""

    __tablename__ = "idempotency_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    scope: Mapped[str] = mapped_column(String(40))  # e.g. "create_order", "payment_attempt"
    resource_id: Mapped[str] = mapped_column(String(36))  # the order_id / payment_attempt_id it resolved to
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
