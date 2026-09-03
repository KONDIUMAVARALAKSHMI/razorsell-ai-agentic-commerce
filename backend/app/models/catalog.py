from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50), index=True)  # laptop | accessory | gaming
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float)  # INR, source of truth
    specs: Mapped[dict] = mapped_column(JSON, default=dict)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    portability_score: Mapped[float] = mapped_column(Float, default=0.5)  # 0-1, higher = more portable
    performance_score: Mapped[float] = mapped_column(Float, default=0.5)  # 0-1, gaming/coding capability
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    inventory: Mapped["Inventory"] = relationship(back_populates="product", uselist=False)


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), unique=True)
    quantity_available: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped["Product"] = relationship(back_populates="inventory")


class ProductRelation(Base):
    """Merchant-curated relationships used ONLY for grounded upsell/cross-sell.
    The AI is never allowed to invent a relation that isn't in this table
    (or the deterministic compatibility scorer)."""

    __tablename__ = "product_relations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"))
    related_product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"))
    relation_type: Mapped[str] = mapped_column(String(20))  # "upsell" | "cross_sell"
    reason: Mapped[str] = mapped_column(String(300))
    bundle_discount_percent: Mapped[float] = mapped_column(Float, default=0.0)
