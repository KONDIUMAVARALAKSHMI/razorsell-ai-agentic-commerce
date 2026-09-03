from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record_event
from app.core.config import get_settings
from app.guardrails.policy import (
    GuardrailContext,
    GuardrailViolation,
    enforce_payment_requires_confirmation,
    enforce_retry_limit,
)
from app.models.cart import Cart
from app.models.catalog import Product
from app.models.orders import IdempotencyKey, Order, OrderItem, PaymentAttempt
from app.payments.base import PaymentProvider
from app.services.cart import get_cart_snapshot

settings = get_settings()


@dataclass
class CheckoutTotals:
    subtotal: float
    discount_amount: float
    total: float
    line_items: list[dict]


def calculate_checkout(db: Session, *, cart: Cart, discount_percent: float = 0.0) -> CheckoutTotals:
    """calculate_checkout() tool. The ONLY place a checkout total is computed.
    Always derives prices from the database, never from client input."""
    from app.guardrails.policy import enforce_discount_within_bounds

    enforce_discount_within_bounds(discount_percent)

    snapshot = get_cart_snapshot(db, cart=cart)
    subtotal = snapshot["subtotal"]
    discount_amount = round(subtotal * (discount_percent / 100.0), 2)
    total = round(subtotal - discount_amount, 2)
    return CheckoutTotals(
        subtotal=subtotal, discount_amount=discount_amount, total=total, line_items=snapshot["items"]
    )


def find_existing_order_for_key(db: Session, idempotency_key: str) -> Order | None:
    """Public lookup used by the API layer to short-circuit duplicate
    checkout submissions before touching the cart at all."""
    existing = db.execute(
        select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key)
    ).scalar_one_or_none()
    if existing is None:
        return None
    return db.get(Order, existing.resource_id)


def create_order(
    db: Session,
    *,
    session_id: str,
    user_id: str,
    cart: Cart,
    discount_percent: float,
    payment_confirmed: bool,
    idempotency_key: str | None = None,
) -> Order:
    """Creates an Order row (state=CREATED) after enforcing explicit
    confirmation (Rule 1). Duplicate calls with the same idempotency_key
    return the SAME order rather than creating a second one (Failure B)."""
    idempotency_key = idempotency_key or f"order_{cart.id}_{uuid.uuid4().hex[:12]}"

    existing_order = find_existing_order_for_key(db, idempotency_key)
    if existing_order is not None:
        record_event(
            db,
            session_id=session_id,
            event_type="DUPLICATE_REQUEST_BLOCKED",
            actor="SYSTEM",
            action="Duplicate create_order request detected via idempotency key.",
            status="BLOCKED",
            order_id=existing_order.id,
            user_id=user_id,
            metadata={"idempotency_key": idempotency_key},
        )
        return existing_order

    ctx = GuardrailContext(session_id=session_id, payment_confirmed=payment_confirmed)
    try:
        enforce_payment_requires_confirmation(ctx)
    except GuardrailViolation as violation:
        record_event(
            db,
            session_id=session_id,
            event_type="GUARDRAIL_BLOCKED",
            actor="SYSTEM",
            action="Blocked create_order: payment not explicitly confirmed.",
            reason=violation.message,
            status="BLOCKED",
            user_id=user_id,
            metadata={"rule": violation.rule},
        )
        # Commit now: the API layer's exception handler converts this
        # violation straight into an HTTP error response without reaching
        # its own db.commit(), so the audit trail must be persisted here or
        # it would be silently rolled back when the session closes.
        db.commit()
        raise

    totals = calculate_checkout(db, cart=cart, discount_percent=discount_percent)
    if not totals.line_items:
        raise GuardrailViolation("EMPTY_CART", "Cannot check out an empty cart.")

    order = Order(
        session_id=session_id,
        user_id=user_id,
        cart_id=cart.id,
        subtotal=totals.subtotal,
        discount_amount=totals.discount_amount,
        total_amount=totals.total,
        status="CREATED",
        idempotency_key=idempotency_key,
    )
    db.add(order)
    db.flush()

    for line in totals.line_items:
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=line["product_id"],
                product_name=line["name"],
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                line_total=line["line_total"],
            )
        )

    db.add(IdempotencyKey(key=idempotency_key, scope="create_order", resource_id=order.id))
    cart.status = "checked_out"
    db.flush()

    record_event(
        db,
        session_id=session_id,
        event_type="CHECKOUT_STARTED",
        actor="SYSTEM",
        action="Order created with server-calculated total.",
        order_id=order.id,
        user_id=user_id,
        metadata={"total_amount": order.total_amount, "idempotency_key": idempotency_key},
    )
    record_event(
        db,
        session_id=session_id,
        event_type="USER_PAYMENT_CONFIRMATION",
        actor="USER",
        action="Customer explicitly confirmed the order total.",
        order_id=order.id,
        user_id=user_id,
    )
    return order


def initiate_payment(
    db: Session,
    *,
    order: Order,
    provider: PaymentProvider,
    simulated_outcome: str | None = None,
) -> PaymentAttempt:
    """create_payment_order() + payment attempt tool. Enforces the retry
    limit (Rule 5) and always records an audit event, success or failure."""
    ctx = GuardrailContext(session_id=order.session_id, retry_count=order.retry_count)
    try:
        enforce_retry_limit(ctx)
    except GuardrailViolation as violation:
        order.status = "RETRY_LIMIT_REACHED"
        db.flush()
        record_event(
            db,
            session_id=order.session_id,
            event_type="RETRY_BLOCKED",
            actor="SYSTEM",
            action="Blocked further payment retry: limit reached.",
            reason=violation.message,
            status="BLOCKED",
            order_id=order.id,
            user_id=order.user_id,
            metadata={"rule": violation.rule, "retry_count": order.retry_count},
        )
        db.commit()
        raise

    if order.razorpay_order_id is None:
        provider_order = provider.create_order(
            amount_rupees=order.total_amount, currency="INR", receipt=order.id
        )
        order.razorpay_order_id = provider_order.provider_order_id
        order.status = "PAYMENT_PENDING"
        db.flush()
        record_event(
            db,
            session_id=order.session_id,
            event_type="RAZORPAY_ORDER_CREATED",
            actor="RAZORPAY" if provider.name == "razorpay" else "SYSTEM",
            action=f"Provider order created ({provider.name}).",
            order_id=order.id,
            user_id=order.user_id,
            metadata={"provider_order_id": order.razorpay_order_id, "provider": provider.name},
        )

    attempt_number = len(order.payment_attempts) + 1
    result = provider.capture_or_verify(
        provider_order_id=order.razorpay_order_id, simulated_outcome=simulated_outcome
    )

    attempt = PaymentAttempt(
        order_id=order.id,
        attempt_number=attempt_number,
        provider=provider.name,
        provider_payment_id=result.provider_payment_id,
        simulated_outcome=simulated_outcome if provider.name == "mock" else None,
        status="SUCCESS" if result.status == "success" else "FAILED",
        failure_reason=result.failure_reason,
    )
    db.add(attempt)
    db.flush()

    record_event(
        db,
        session_id=order.session_id,
        event_type="PAYMENT_ATTEMPTED",
        actor="SYSTEM",
        action=f"Payment attempt #{attempt_number} via {provider.name}.",
        order_id=order.id,
        user_id=order.user_id,
        metadata={"attempt_number": attempt_number},
    )

    if result.status == "success":
        order.status = "SUCCESS"
        order.retry_count = 0
        db.flush()
        record_event(
            db,
            session_id=order.session_id,
            event_type="PAYMENT_SUCCESS",
            actor="RAZORPAY" if provider.name == "razorpay" else "SYSTEM",
            action="Payment verified successfully.",
            order_id=order.id,
            user_id=order.user_id,
            metadata={"provider_payment_id": result.provider_payment_id},
        )
    else:
        order.retry_count += 1
        if order.retry_count >= settings.MAX_PAYMENT_RETRIES:
            order.status = "RETRY_LIMIT_REACHED"
        else:
            order.status = "RETRY_ALLOWED"
        db.flush()
        record_event(
            db,
            session_id=order.session_id,
            event_type="PAYMENT_FAILED",
            actor="SYSTEM",
            action="Payment attempt failed.",
            reason=result.failure_reason or "Unknown failure",
            status="ERROR",
            order_id=order.id,
            user_id=order.user_id,
            metadata={"retry_count": order.retry_count},
        )

    return attempt


def request_retry(db: Session, *, order: Order) -> Order:
    """request_payment_retry() tool. Only allowed from RETRY_ALLOWED / FAILED
    states, and always gated by the same retry-limit guardrail."""
    if order.status not in {"RETRY_ALLOWED", "FAILED"}:
        record_event(
            db,
            session_id=order.session_id,
            event_type="RETRY_BLOCKED",
            actor="SYSTEM",
            action="Blocked retry request: order is not in a retryable state.",
            reason=f"Order status is {order.status}, not RETRY_ALLOWED or FAILED.",
            status="BLOCKED",
            order_id=order.id,
            user_id=order.user_id,
            metadata={"order_status": order.status, "retry_count": order.retry_count},
        )
        db.commit()
        raise GuardrailViolation(
            "INVALID_STATE_TRANSITION",
            f"Cannot retry an order in status {order.status}.",
        )
    record_event(
        db,
        session_id=order.session_id,
        event_type="RETRY_REQUESTED",
        actor="USER",
        action="Customer requested a payment retry.",
        order_id=order.id,
        user_id=order.user_id,
        metadata={"retry_count": order.retry_count},
    )
    order.status = "PAYMENT_PENDING"
    db.flush()
    return order


def get_order_status(db: Session, order_id: str) -> Order | None:
    return db.get(Order, order_id)
