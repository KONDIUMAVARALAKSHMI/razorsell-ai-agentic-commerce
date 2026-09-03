from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import guarded
from app.audit.service import record_event
from app.core.db import get_db
from app.payments.factory import get_payment_provider
from app.schemas.api import GenericResponse, PaymentAttemptRequest, RazorpayVerifyRequest, RetryRequest
from app.services import checkout as checkout_service

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.post("/attempt", response_model=GenericResponse)
def attempt_payment(payload: PaymentAttemptRequest, db: Session = Depends(get_db)):
    """Executes a payment attempt against the configured provider. When
    PAYMENT_PROVIDER=mock, `simulated_outcome` lets the demo/eval harness
    force SUCCESS / FAILURE / TIMEOUT / DUPLICATE_REQUEST deterministically."""
    with guarded():
        order = checkout_service.get_order_status(db, payload.order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found.")
        provider = get_payment_provider()
        attempt = checkout_service.initiate_payment(
            db, order=order, provider=provider, simulated_outcome=payload.simulated_outcome
        )
        db.commit()
        return GenericResponse(
            ok=True,
            data={
                "order_status": order.status,
                "attempt_status": attempt.status,
                "failure_reason": attempt.failure_reason,
                "retry_count": order.retry_count,
            },
        )


@router.post("/verify", response_model=GenericResponse)
def verify_razorpay_payment(payload: RazorpayVerifyRequest, db: Session = Depends(get_db)):
    """Server-side signature verification for the real Razorpay Test Mode
    checkout handoff (frontend Razorpay Checkout -> this endpoint)."""
    with guarded():
        from app.payments.razorpay_provider import RazorpayPaymentProvider

        order = checkout_service.get_order_status(db, payload.order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found.")

        provider = RazorpayPaymentProvider()
        is_valid = provider.verify_payment_signature(
            razorpay_order_id=payload.razorpay_order_id,
            razorpay_payment_id=payload.razorpay_payment_id,
            razorpay_signature=payload.razorpay_signature,
        )
        if is_valid:
            order.status = "SUCCESS"
            db.commit()
            record_event(
                db,
                session_id=order.session_id,
                event_type="PAYMENT_SUCCESS",
                actor="RAZORPAY",
                action="Signature verified server-side.",
                order_id=order.id,
                user_id=order.user_id,
            )
            db.commit()
            return GenericResponse(ok=True, data={"status": "SUCCESS"})

        order.status = "FAILED"
        db.commit()
        record_event(
            db,
            session_id=order.session_id,
            event_type="PAYMENT_FAILED",
            actor="SYSTEM",
            action="Signature verification failed.",
            status="ERROR",
            order_id=order.id,
            user_id=order.user_id,
        )
        db.commit()
        return GenericResponse(ok=False, error="Signature verification failed.")


@router.post("/retry", response_model=GenericResponse)
def retry_payment(payload: RetryRequest, db: Session = Depends(get_db)):
    with guarded():
        order = checkout_service.get_order_status(db, payload.order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found.")
        order = checkout_service.request_retry(db, order=order)
        db.commit()
        return GenericResponse(ok=True, data={"status": order.status})
