from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Every event type the system is allowed to emit. Keeping this closed list
# (rather than free-text) makes the audit trail queryable and makes it easy
# to assert, in tests, that only expected events were ever recorded.
AUDIT_EVENT_TYPES = (
    "USER_MESSAGE",
    "AI_DECISION",
    "PRODUCT_SEARCH",
    "PRODUCT_RECOMMENDATION",
    "UPSELL_RECOMMENDATION",
    "UPSELL_ACCEPTED",
    "UPSELL_REJECTED",
    "CART_UPDATED",
    "CHECKOUT_STARTED",
    "USER_PAYMENT_CONFIRMATION",
    "RAZORPAY_ORDER_CREATED",
    "PAYMENT_ATTEMPTED",
    "PAYMENT_SUCCESS",
    "PAYMENT_FAILED",
    "RETRY_REQUESTED",
    "RETRY_BLOCKED",
    "GUARDRAIL_BLOCKED",
    "INVENTORY_BLOCKED",
    "DUPLICATE_REQUEST_BLOCKED",
)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    actor: Mapped[str] = mapped_column(String(10))  # USER | AI | SYSTEM | RAZORPAY
    action: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="OK")  # OK | BLOCKED | ERROR
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
