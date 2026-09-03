from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import guarded
from app.core.db import get_db
from app.models.audit import AuditEvent
from app.schemas.api import GenericResponse

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/events", response_model=GenericResponse)
def list_events(
    session_id: Optional[str] = None,
    order_id: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    actor: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    with guarded():
        stmt = select(AuditEvent).order_by(AuditEvent.timestamp.asc())
        if session_id:
            stmt = stmt.where(AuditEvent.session_id == session_id)
        if order_id:
            stmt = stmt.where(AuditEvent.order_id == order_id)
        if event_type:
            stmt = stmt.where(AuditEvent.event_type == event_type)
        if status:
            stmt = stmt.where(AuditEvent.status == status)
        if actor:
            stmt = stmt.where(AuditEvent.actor == actor)
        stmt = stmt.limit(limit)
        events = db.execute(stmt).scalars().all()
        return GenericResponse(
            ok=True,
            data=[
                {
                    "event_id": e.event_id,
                    "timestamp": e.timestamp.isoformat(),
                    "session_id": e.session_id,
                    "user_id": e.user_id,
                    "order_id": e.order_id,
                    "event_type": e.event_type,
                    "actor": e.actor,
                    "action": e.action,
                    "reason": e.reason,
                    "status": e.status,
                    "metadata": e.event_metadata,
                }
                for e in events
            ],
        )
