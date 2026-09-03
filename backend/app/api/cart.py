from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import ensure_user, guarded
from app.audit.service import record_event
from app.core.db import get_db
from app.models.agent import Recommendation
from app.schemas.api import CartActionRequest, GenericResponse, UpsellDecisionRequest
from app.services import cart as cart_service

router = APIRouter(prefix="/api/v1/cart", tags=["cart"])


@router.get("/{session_id}", response_model=GenericResponse)
def get_cart(session_id: str, user_id: str, db: Session = Depends(get_db)):
    with guarded():
        ensure_user(db, user_id)
        cart = cart_service.get_or_create_cart(db, session_id=session_id, user_id=user_id)
        db.commit()
        return GenericResponse(ok=True, data=cart_service.get_cart_snapshot(db, cart=cart))


@router.post("/add", response_model=GenericResponse)
def add_item(payload: CartActionRequest, db: Session = Depends(get_db)):
    with guarded():
        ensure_user(db, payload.user_id)
        cart = cart_service.get_or_create_cart(db, session_id=payload.session_id, user_id=payload.user_id)
        cart_service.add_to_cart(db, cart=cart, product_id=payload.product_id, quantity=payload.quantity)
        record_event(
            db,
            session_id=payload.session_id,
            event_type="CART_UPDATED",
            actor="USER",
            action="Item added to cart.",
            user_id=payload.user_id,
            metadata={"product_id": payload.product_id, "quantity": payload.quantity},
        )
        db.commit()
        return GenericResponse(ok=True, data=cart_service.get_cart_snapshot(db, cart=cart))


@router.post("/remove", response_model=GenericResponse)
def remove_item(payload: CartActionRequest, db: Session = Depends(get_db)):
    with guarded():
        ensure_user(db, payload.user_id)
        cart = cart_service.get_or_create_cart(db, session_id=payload.session_id, user_id=payload.user_id)
        cart_service.remove_from_cart(db, cart=cart, product_id=payload.product_id)
        record_event(
            db,
            session_id=payload.session_id,
            event_type="CART_UPDATED",
            actor="USER",
            action="Item removed from cart.",
            user_id=payload.user_id,
            metadata={"product_id": payload.product_id},
        )
        db.commit()
        return GenericResponse(ok=True, data=cart_service.get_cart_snapshot(db, cart=cart))


@router.post("/update-quantity", response_model=GenericResponse)
def update_quantity(payload: CartActionRequest, db: Session = Depends(get_db)):
    with guarded():
        ensure_user(db, payload.user_id)
        cart = cart_service.get_or_create_cart(db, session_id=payload.session_id, user_id=payload.user_id)
        cart_service.update_quantity(db, cart=cart, product_id=payload.product_id, quantity=payload.quantity)
        record_event(
            db,
            session_id=payload.session_id,
            event_type="CART_UPDATED",
            actor="USER",
            action="Cart quantity updated.",
            user_id=payload.user_id,
            metadata={"product_id": payload.product_id, "quantity": payload.quantity},
        )
        db.commit()
        return GenericResponse(ok=True, data=cart_service.get_cart_snapshot(db, cart=cart))


@router.post("/upsell-decision", response_model=GenericResponse)
def upsell_decision(payload: UpsellDecisionRequest, db: Session = Depends(get_db)):
    with guarded():
        ensure_user(db, payload.user_id)
        cart = cart_service.get_or_create_cart(db, session_id=payload.session_id, user_id=payload.user_id)
        if payload.accept:
            cart_service.add_to_cart(
                db, cart=cart, product_id=payload.product_id, quantity=1, added_via="upsell_accept"
            )
            event_type = "UPSELL_ACCEPTED"
            action = "Customer accepted upsell recommendation."
        else:
            event_type = "UPSELL_REJECTED"
            action = "Customer declined upsell recommendation."

        from sqlalchemy import select

        rec = db.execute(
            select(Recommendation)
            .where(Recommendation.product_id == payload.product_id)
            .order_by(Recommendation.created_at.desc())
        ).scalars().first()
        if rec is not None:
            rec.accepted = payload.accept

        record_event(
            db,
            session_id=payload.session_id,
            event_type=event_type,
            actor="USER",
            action=action,
            user_id=payload.user_id,
            metadata={"product_id": payload.product_id},
        )
        db.commit()
        return GenericResponse(ok=True, data=cart_service.get_cart_snapshot(db, cart=cart))
