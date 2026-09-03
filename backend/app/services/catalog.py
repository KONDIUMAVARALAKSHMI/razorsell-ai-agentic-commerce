from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.ai_provider import ExtractedIntent
from app.models.catalog import Inventory, Product
from app.services.scoring import ScoredProduct, rank_products


def _available_qty(db: Session, product_id: str) -> int:
    inv = db.execute(select(Inventory).where(Inventory.product_id == product_id)).scalar_one_or_none()
    if inv is None:
        return 0
    return max(0, inv.quantity_available - inv.reserved)


def search_products(db: Session, intent: ExtractedIntent, limit: int = 5) -> list[ScoredProduct]:
    """search_products() tool: the ONLY way the agent may look up products.
    Always grounded in the database - never returns an invented product."""
    stmt = select(Product).where(Product.is_active.is_(True))
    if intent.category:
        stmt = stmt.where(Product.category == intent.category)
    products = db.execute(stmt).scalars().all()
    products_with_stock = [(p, _available_qty(db, p.id)) for p in products]
    ranked = rank_products(products_with_stock, intent)
    # Filter out-of-stock items from what's shown as a "recommendation",
    # but keep them retrievable via get_product_details for transparency.
    in_stock_ranked = [s for s in ranked if _available_qty(db, s.product.id) > 0]
    return in_stock_ranked[:limit]


def get_product(db: Session, product_id: str) -> Product | None:
    """get_product_details() tool."""
    return db.get(Product, product_id)


def get_product_by_sku(db: Session, sku: str) -> Product | None:
    return db.execute(select(Product).where(Product.sku == sku)).scalar_one_or_none()


def compare_products(db: Session, product_ids: list[str]) -> list[Product]:
    """compare_products() tool. Only returns products that actually exist;
    silently drops any id that doesn't resolve (never fabricates a row)."""
    products = []
    for pid in product_ids:
        p = db.get(Product, pid)
        if p is not None:
            products.append(p)
    return products


def check_inventory(db: Session, product_id: str) -> int:
    """check_inventory() tool. Returns units available for sale right now."""
    return _available_qty(db, product_id)
