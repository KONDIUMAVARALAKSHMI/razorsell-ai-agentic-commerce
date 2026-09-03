from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.factory import get_ai_provider
from app.agents.orchestrator import handle_customer_message, select_product
from app.api.deps import ensure_user, guarded
from app.core.db import get_db
from app.schemas.api import ChatRequest, SelectProductRequest, GenericResponse

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/message", response_model=GenericResponse)
def send_message(payload: ChatRequest, db: Session = Depends(get_db)):
    with guarded():
        ensure_user(db, payload.user_id)
        ai = get_ai_provider()
        result = handle_customer_message(
            db, ai=ai, session_id=payload.session_id, user_id=payload.user_id, message=payload.message
        )
        db.commit()
        return GenericResponse(ok=True, data=result)


@router.post("/select-product", response_model=GenericResponse)
def select_product_endpoint(payload: SelectProductRequest, db: Session = Depends(get_db)):
    with guarded():
        ensure_user(db, payload.user_id)
        ai = get_ai_provider()
        result = select_product(
            db, ai=ai, session_id=payload.session_id, user_id=payload.user_id, product_id=payload.product_id
        )
        db.commit()
        return GenericResponse(ok=True, data=result)
