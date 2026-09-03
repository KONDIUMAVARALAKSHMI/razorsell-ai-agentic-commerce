from __future__ import annotations

import pytest

from app.guardrails.policy import (
    GuardrailContext,
    GuardrailViolation,
    enforce_discount_within_bounds,
    enforce_max_upsell,
    enforce_payment_requires_confirmation,
    enforce_retry_limit,
)
from app.services import cart as cart_service
from app.services import checkout as checkout_service
from tests.conftest import new_session_id, new_user_id


def _seed_one_product(db_session):
    from scripts.seed_database import LAPTOPS, _upsert_product

    return _upsert_product(db_session, LAPTOPS[0], "laptop")


class TestGuardrailPolicy:
    def test_max_upsell_blocks_beyond_configured_limit(self):
        ctx = GuardrailContext(session_id="s1", upsell_count_this_checkout=2)
        with pytest.raises(GuardrailViolation) as exc_info:
            enforce_max_upsell(ctx)
        assert exc_info.value.rule == "RULE_4_MAX_UPSELL"

    def test_max_upsell_allows_under_limit(self):
        ctx = GuardrailContext(session_id="s1", upsell_count_this_checkout=1)
        enforce_max_upsell(ctx)  # should not raise

    def test_payment_requires_explicit_confirmation(self):
        ctx = GuardrailContext(session_id="s1", payment_confirmed=False)
        with pytest.raises(GuardrailViolation) as exc_info:
            enforce_payment_requires_confirmation(ctx)
        assert exc_info.value.rule == "RULE_1_EXPLICIT_CONFIRMATION"

    def test_payment_confirmed_passes(self):
        ctx = GuardrailContext(session_id="s1", payment_confirmed=True)
        enforce_payment_requires_confirmation(ctx)  # should not raise

    def test_retry_limit_enforced(self):
        ctx = GuardrailContext(session_id="s1", retry_count=3)
        with pytest.raises(GuardrailViolation) as exc_info:
            enforce_retry_limit(ctx)
        assert exc_info.value.rule == "RULE_5_RETRY_LIMIT"

    def test_discount_within_bounds_rejects_excessive_discount(self):
        with pytest.raises(GuardrailViolation) as exc_info:
            enforce_discount_within_bounds(50.0)
        assert exc_info.value.rule == "RULE_2_DISCOUNT_BOUNDS"

    def test_discount_within_bounds_rejects_negative(self):
        with pytest.raises(GuardrailViolation):
            enforce_discount_within_bounds(-5.0)

    def test_discount_within_bounds_allows_valid_value(self):
        enforce_discount_within_bounds(3.0)  # should not raise


class TestPaymentAmountCalculation:
    def test_checkout_total_uses_server_price_not_client_supplied(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()
        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()

        totals = checkout_service.calculate_checkout(db_session, cart=cart, discount_percent=0.0)
        assert totals.subtotal == pytest.approx(product.price)
        assert totals.total == pytest.approx(product.price)

    def test_discount_applied_correctly(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()
        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()

        totals = checkout_service.calculate_checkout(db_session, cart=cart, discount_percent=5.0)
        expected_discount = round(product.price * 0.05, 2)
        assert totals.discount_amount == pytest.approx(expected_discount)
        assert totals.total == pytest.approx(product.price - expected_discount)

    def test_excessive_discount_is_rejected(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()
        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()

        with pytest.raises(GuardrailViolation) as exc_info:
            checkout_service.calculate_checkout(db_session, cart=cart, discount_percent=99.0)
        assert exc_info.value.rule == "RULE_2_DISCOUNT_BOUNDS"

    def test_empty_cart_cannot_check_out(self, db_session):
        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        db_session.commit()
        with pytest.raises(GuardrailViolation) as exc_info:
            checkout_service.create_order(
                db_session,
                session_id=cart.session_id,
                user_id=cart.user_id,
                cart=cart,
                discount_percent=0.0,
                payment_confirmed=True,
            )
        assert exc_info.value.rule == "EMPTY_CART"

    def test_order_cannot_be_created_without_confirmation(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()
        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()

        with pytest.raises(GuardrailViolation) as exc_info:
            checkout_service.create_order(
                db_session,
                session_id=cart.session_id,
                user_id=cart.user_id,
                cart=cart,
                discount_percent=0.0,
                payment_confirmed=False,
            )
        assert exc_info.value.rule == "RULE_1_EXPLICIT_CONFIRMATION"
