"""
The audit log is the system's source of truth for "what happened and why".
This is the ONLY function anywhere in the codebase that is allowed to insert
into audit_events, so every financial or AI action is guaranteed to leave a
trace (Acceptance criteria: Rule 8 - "Every financial action must produce an
audit event").
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def record_event(
    db: Session,
    *,
    session_id: str,
    event_type: str,
    actor: str,
    action: str,
    reason: str = "",
    status: str = "OK",
    user_id: Optional[str] = None,
    order_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> AuditEvent:
    event = AuditEvent(
        session_id=session_id,
        user_id=user_id,
        order_id=order_id,
        event_type=event_type,
        actor=actor,
        action=action,
        reason=reason,
        status=status,
        event_metadata=metadata or {},
    )
    db.add(event)
    db.flush()
    return event
