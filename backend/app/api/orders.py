from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import guarded
from app.core.db import get_db
from app.models.orders import Order
from app.schemas.api import GenericResponse

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def _serialize_order(order: Order) -> dict:
    return {
        "id": order.id,
        "status": order.status,
        "subtotal": order.subtotal,
        "discount_amount": order.discount_amount,
        "total_amount": order.total_amount,
        "retry_count": order.retry_count,
        "razorpay_order_id": order.razorpay_order_id,
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "product_name": i.product_name,
                "quantity": i.quantity,
                "unit_price": i.unit_price,
                "line_total": i.line_total,
            }
            for i in order.items
        ],
        "payment_attempts": [
            {
                "attempt_number": a.attempt_number,
                "provider": a.provider,
                "status": a.status,
                "failure_reason": a.failure_reason,
                "created_at": a.created_at.isoformat(),
            }
            for a in order.payment_attempts
        ],
    }


@router.get("/{order_id}", response_model=GenericResponse)
def get_order(order_id: str, db: Session = Depends(get_db)):
    with guarded():
        order = db.get(Order, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found.")
        return GenericResponse(ok=True, data=_serialize_order(order))


@router.get("", response_model=GenericResponse)
def list_orders(limit: int = 50, db: Session = Depends(get_db)):
    with guarded():
        orders = db.execute(select(Order).order_by(Order.created_at.desc()).limit(limit)).scalars().all()
        return GenericResponse(ok=True, data=[_serialize_order(o) for o in orders])
