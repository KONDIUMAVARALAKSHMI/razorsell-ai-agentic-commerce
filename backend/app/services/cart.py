from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.guardrails.policy import GuardrailViolation, enforce_inventory_available, enforce_product_exists
from app.models.cart import Cart, CartItem
from app.models.catalog import Product
from app.services.catalog import check_inventory


def get_or_create_cart(db: Session, *, session_id: str, user_id: str) -> Cart:
    cart = db.execute(
        select(Cart).where(Cart.session_id == session_id, Cart.status == "open")
    ).scalar_one_or_none()
    if cart is None:
        cart = Cart(session_id=session_id, user_id=user_id, status="open")
        db.add(cart)
        db.flush()
    return cart


def _get_cart_item(db: Session, *, cart_id: str, product_id: str) -> CartItem | None:
    return db.execute(
        select(CartItem).where(CartItem.cart_id == cart_id, CartItem.product_id == product_id)
    ).scalar_one_or_none()


def add_to_cart(db: Session, *, cart: Cart, product_id: str, quantity: int, added_via: str = "user") -> CartItem:
    if quantity <= 0:
        raise GuardrailViolation("INVALID_QUANTITY", "Quantity must be a positive integer.")

    product = db.get(Product, product_id)
    enforce_product_exists(product)

    existing_item = _get_cart_item(db, cart_id=cart.id, product_id=product_id)
    existing_qty = existing_item.quantity if existing_item else 0
    available = check_inventory(db, product_id)
    enforce_inventory_available(available, existing_qty + quantity)

    if existing_item:
        existing_item.quantity += quantity
        db.flush()
        return existing_item

    item = CartItem(
        cart_id=cart.id,
        product_id=product_id,
        quantity=quantity,
        price_at_add=product.price,
        added_via=added_via,
    )
    db.add(item)
    db.flush()
    return item


def remove_from_cart(db: Session, *, cart: Cart, product_id: str) -> None:
    item = _get_cart_item(db, cart_id=cart.id, product_id=product_id)
    if item is not None:
        db.delete(item)
        db.flush()


def update_quantity(db: Session, *, cart: Cart, product_id: str, quantity: int) -> CartItem | None:
    if quantity <= 0:
        remove_from_cart(db, cart=cart, product_id=product_id)
        return None
    item = _get_cart_item(db, cart_id=cart.id, product_id=product_id)
    if item is None:
        raise GuardrailViolation("ITEM_NOT_IN_CART", "Cannot update quantity for an item not in the cart.")
    available = check_inventory(db, product_id)
    enforce_inventory_available(available, quantity)
    item.quantity = quantity
    db.flush()
    return item


def clear_cart(db: Session, *, cart: Cart) -> None:
    items = db.execute(select(CartItem).where(CartItem.cart_id == cart.id)).scalars().all()
    for item in items:
        db.delete(item)
    db.flush()


def get_cart_snapshot(db: Session, *, cart: Cart) -> dict:
    """Returns a fully server-priced snapshot. Prices ALWAYS come from the
    live Product row, never from price_at_add or any client-supplied value.

    Queries CartItem directly by cart_id rather than via cart.items so this
    is correct even when called in the same transaction as a just-completed
    add/remove (the in-memory relationship collection on `cart` is not
    guaranteed to reflect writes made via db.add() until the object is
    refreshed or the session is committed and re-queried).
    """
    items = db.execute(select(CartItem).where(CartItem.cart_id == cart.id)).scalars().all()
    lines = []
    subtotal = 0.0
    for item in items:
        product = db.get(Product, item.product_id)
        if product is None:
            continue
        line_total = product.price * item.quantity
        subtotal += line_total
        lines.append(
            {
                "product_id": product.id,
                "name": product.name,
                "unit_price": product.price,
                "quantity": item.quantity,
                "line_total": line_total,
                "added_via": item.added_via,
            }
        )
    return {"cart_id": cart.id, "items": lines, "subtotal": round(subtotal, 2)}
