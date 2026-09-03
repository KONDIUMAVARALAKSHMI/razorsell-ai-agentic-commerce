from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """A customer using the shopping agent. Kept intentionally minimal -
    this is a demo commerce agent, not an identity system."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(String(120), default="Guest")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Merchant(Base):
    """The single seeded merchant for the demo. A real multi-tenant version
    would scope every table by merchant_id; kept to one merchant here to
    keep the demo focused, and documented as a known limitation."""

    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
