from __future__ import annotations

from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.guardrails.policy import GuardrailViolation
from app.models.users import User


def ensure_user(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id, display_name="Guest")
        db.add(user)
        db.flush()
    return user


@contextmanager
def guarded():
    """Converts a GuardrailViolation into a 403 with the safe, user-facing
    message rather than a raw exception. Any other unexpected error becomes
    a generic 500 - we never leak stack traces or internals to the client."""
    try:
        yield
    except GuardrailViolation as violation:
        raise HTTPException(status_code=403, detail={"rule": violation.rule, "message": violation.message})
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive catch-all
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") from exc
