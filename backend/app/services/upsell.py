from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.catalog import Product, ProductRelation
from app.services.catalog import check_inventory

settings = get_settings()


@dataclass
class UpsellCandidate:
    product: Product
    relation_type: str
    reason: str
    bundle_discount_percent: float


def get_upsell_candidates(db: Session, *, product_id: str, already_shown: int) -> list[UpsellCandidate]:
    """Returns at most (MAX_UPSELL_RECOMMENDATIONS - already_shown) candidates.

    Rule: every candidate must come from a merchant-curated ProductRelation
    row (grounded relationship) - the AI cannot invent a compatible product.
    Out-of-stock candidates are excluded.
    """
    remaining_slots = max(0, settings.MAX_UPSELL_RECOMMENDATIONS - already_shown)
    if remaining_slots == 0:
        return []

    relations = db.execute(
        select(ProductRelation).where(ProductRelation.product_id == product_id)
    ).scalars().all()

    candidates: list[UpsellCandidate] = []
    for rel in relations:
        related_product = db.get(Product, rel.related_product_id)
        if related_product is None or not related_product.is_active:
            continue
        if check_inventory(db, related_product.id) <= 0:
            continue
        candidates.append(
            UpsellCandidate(
                product=related_product,
                relation_type=rel.relation_type,
                reason=rel.reason,
                bundle_discount_percent=rel.bundle_discount_percent,
            )
        )

    return candidates[:remaining_slots]
