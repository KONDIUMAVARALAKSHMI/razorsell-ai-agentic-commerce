from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import ensure_user, guarded
from app.core.db import get_db
from app.schemas.api import CheckoutConfirmRequest, GenericResponse
from app.services import cart as cart_service
from app.services import checkout as checkout_service

router = APIRouter(prefix="/api/v1/checkout", tags=["checkout"])


@router.get("/preview", response_model=GenericResponse)
def preview(session_id: str, user_id: str, discount_percent: float = 0.0, db: Session = Depends(get_db)):
    with guarded():
        ensure_user(db, user_id)
        cart = cart_service.get_or_create_cart(db, session_id=session_id, user_id=user_id)
        totals = checkout_service.calculate_checkout(db, cart=cart, discount_percent=discount_percent)
        return GenericResponse(
            ok=True,
            data={
                "subtotal": totals.subtotal,
                "discount_amount": totals.discount_amount,
                "total": totals.total,
                "line_items": totals.line_items,
            },
        )


@router.post("/confirm", response_model=GenericResponse)
def confirm(payload: CheckoutConfirmRequest, db: Session = Depends(get_db)):
    """This is the ONLY endpoint that can create an Order, and it requires
    confirm=true from the frontend's explicit 'Confirm & Proceed to Payment'
    button click - the LLM cannot call this on the user's behalf.

    Idempotency: if the client supplies the same idempotency_key as a prior
    call (e.g. a network-retried double submit), the ORIGINAL order is
    returned rather than creating a duplicate - checked before touching the
    cart at all, so it holds even after the cart has since moved on.
    """
    with guarded():
        ensure_user(db, payload.user_id)

        if payload.idempotency_key:
            existing = checkout_service.find_existing_order_for_key(db, payload.idempotency_key)
            if existing is not None:
                return GenericResponse(
                    ok=True,
                    data={
                        "order_id": existing.id,
                        "status": existing.status,
                        "total_amount": existing.total_amount,
                        "razorpay_order_id": existing.razorpay_order_id,
                    },
                )

        cart = cart_service.get_or_create_cart(db, session_id=payload.session_id, user_id=payload.user_id)
        order = checkout_service.create_order(
            db,
            session_id=payload.session_id,
            user_id=payload.user_id,
            cart=cart,
            discount_percent=payload.discount_percent,
            payment_confirmed=payload.confirm,
            idempotency_key=payload.idempotency_key,
        )
        db.commit()
        return GenericResponse(
            ok=True,
            data={
                "order_id": order.id,
                "status": order.status,
                "total_amount": order.total_amount,
                "razorpay_order_id": order.razorpay_order_id,
            },
        )
