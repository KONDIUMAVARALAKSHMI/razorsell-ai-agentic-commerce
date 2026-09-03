from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import guarded
from app.core.db import get_db
from app.services import catalog as catalog_service

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/products")
def list_products(category: str | None = None, db: Session = Depends(get_db)):
    from sqlalchemy import select

    from app.models.catalog import Product

    stmt = select(Product).where(Product.is_active.is_(True))
    if category:
        stmt = stmt.where(Product.category == category)
    products = db.execute(stmt).scalars().all()
    return [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "price": p.price,
            "description": p.description,
            "specs": p.specs,
            "tags": p.tags,
            "inventory": catalog_service.check_inventory(db, p.id),
        }
        for p in products
    ]


@router.get("/products/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    with guarded():
        product = catalog_service.get_product(db, product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found.")
        return {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "category": product.category,
            "price": product.price,
            "description": product.description,
            "specs": product.specs,
            "tags": product.tags,
            "inventory": catalog_service.check_inventory(db, product.id),
        }


@router.post("/compare")
def compare(product_ids: list[str], db: Session = Depends(get_db)):
    products = catalog_service.compare_products(db, product_ids)
    return [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "specs": p.specs,
            "inventory": catalog_service.check_inventory(db, p.id),
        }
        for p in products
    ]
