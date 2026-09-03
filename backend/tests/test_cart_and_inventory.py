from __future__ import annotations

import pytest

from app.guardrails.policy import GuardrailViolation
from app.services import cart as cart_service
from tests.conftest import new_session_id, new_user_id


def _seed_one_product(db_session):
    from scripts.seed_database import LAPTOPS, _upsert_product

    return _upsert_product(db_session, LAPTOPS[0], "laptop")


class TestCartCalculations:
    def test_add_to_cart_computes_correct_subtotal(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()

        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=2)
        db_session.commit()

        snapshot = cart_service.get_cart_snapshot(db_session, cart=cart)
        assert snapshot["subtotal"] == pytest.approx(product.price * 2)
        assert len(snapshot["items"]) == 1
        assert snapshot["items"][0]["quantity"] == 2

    def test_adding_same_product_twice_increments_quantity(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()

        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=2)
        db_session.commit()

        snapshot = cart_service.get_cart_snapshot(db_session, cart=cart)
        assert len(snapshot["items"]) == 1
        assert snapshot["items"][0]["quantity"] == 3

    def test_prices_always_come_from_live_product_row(self, db_session):
        """Even if price_at_add is stale, the snapshot must reflect the
        CURRENT product.price - the checkout total is never trusted from
        a cached/client value."""
        product = _seed_one_product(db_session)
        db_session.commit()

        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()

        # Simulate a price change after the item was added.
        product.price = product.price + 5000
        db_session.commit()

        snapshot = cart_service.get_cart_snapshot(db_session, cart=cart)
        assert snapshot["items"][0]["unit_price"] == product.price
        assert snapshot["subtotal"] == pytest.approx(product.price)

    def test_remove_from_cart(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()
        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()

        cart_service.remove_from_cart(db_session, cart=cart, product_id=product.id)
        db_session.commit()
        snapshot = cart_service.get_cart_snapshot(db_session, cart=cart)
        assert snapshot["items"] == []
        assert snapshot["subtotal"] == 0.0

    def test_update_quantity_to_zero_removes_item(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()
        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=2)
        db_session.commit()

        cart_service.update_quantity(db_session, cart=cart, product_id=product.id, quantity=0)
        db_session.commit()
        snapshot = cart_service.get_cart_snapshot(db_session, cart=cart)
        assert snapshot["items"] == []


class TestInventoryValidation:
    def test_cannot_add_more_than_available_inventory(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()
        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())

        with pytest.raises(GuardrailViolation) as exc_info:
            cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=9999)
        assert exc_info.value.rule == "INVENTORY_CHECK"

    def test_cannot_add_hallucinated_product(self, db_session):
        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        with pytest.raises(GuardrailViolation) as exc_info:
            cart_service.add_to_cart(db_session, cart=cart, product_id="does-not-exist", quantity=1)
        assert exc_info.value.rule == "RULE_3_NO_HALLUCINATED_PRODUCTS"

    def test_cannot_add_zero_or_negative_quantity(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()
        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        with pytest.raises(GuardrailViolation) as exc_info:
            cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=0)
        assert exc_info.value.rule == "INVALID_QUANTITY"

    def test_cumulative_quantity_across_multiple_adds_respects_inventory(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()
        # Inventory is seeded at 25 units (see scripts/seed_database.INVENTORY_DEFAULT).
        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=20)
        db_session.commit()
        with pytest.raises(GuardrailViolation):
            cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=10)
