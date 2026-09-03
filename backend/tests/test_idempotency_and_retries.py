from __future__ import annotations

import uuid

import pytest

from app.guardrails.policy import GuardrailViolation
from app.payments.mock_provider import MockPaymentProvider
from app.services import cart as cart_service
from app.services import checkout as checkout_service
from tests.conftest import new_session_id, new_user_id


def _seed_one_product(db_session):
    from scripts.seed_database import LAPTOPS, _upsert_product

    return _upsert_product(db_session, LAPTOPS[0], "laptop")


def _cart_with_product(db_session):
    product = _seed_one_product(db_session)
    db_session.commit()
    session_id = new_session_id()
    user_id = new_user_id()
    cart = cart_service.get_or_create_cart(db_session, session_id=session_id, user_id=user_id)
    cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
    db_session.commit()
    return cart, session_id, user_id


class TestIdempotency:
    def test_same_idempotency_key_returns_same_order(self, db_session):
        cart, session_id, user_id = _cart_with_product(db_session)
        key = str(uuid.uuid4())

        order1 = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart,
            discount_percent=0.0, payment_confirmed=True, idempotency_key=key,
        )
        db_session.commit()

        order2 = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart,
            discount_percent=0.0, payment_confirmed=True, idempotency_key=key,
        )
        db_session.commit()

        assert order1.id == order2.id

    def test_different_idempotency_keys_create_different_orders(self, db_session):
        from scripts.seed_database import LAPTOPS, _upsert_product

        cart, session_id, user_id = _cart_with_product(db_session)
        order1 = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart,
            discount_percent=0.0, payment_confirmed=True, idempotency_key=str(uuid.uuid4()),
        )
        db_session.commit()

        # A second, genuinely new cart/checkout in the same session, for a
        # DIFFERENT product (re-upserting the same SKU would delete a product
        # that already has cart/order rows referencing it, which is its own
        # separate concern from what this test is verifying).
        product2 = _upsert_product(db_session, LAPTOPS[1], "laptop")
        db_session.commit()
        cart2 = cart_service.get_or_create_cart(db_session, session_id=session_id, user_id=user_id)
        cart_service.add_to_cart(db_session, cart=cart2, product_id=product2.id, quantity=1)
        db_session.commit()

        order2 = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart2,
            discount_percent=0.0, payment_confirmed=True, idempotency_key=str(uuid.uuid4()),
        )
        db_session.commit()

        assert order1.id != order2.id

    def test_duplicate_order_creation_does_not_duplicate_order_items(self, db_session):
        cart, session_id, user_id = _cart_with_product(db_session)
        key = str(uuid.uuid4())
        for _ in range(3):
            checkout_service.create_order(
                db_session, session_id=session_id, user_id=user_id, cart=cart,
                discount_percent=0.0, payment_confirmed=True, idempotency_key=key,
            )
            db_session.commit()

        from sqlalchemy import select
        from app.models.orders import Order

        orders = db_session.execute(select(Order).where(Order.idempotency_key == key)).scalars().all()
        assert len(orders) == 1


class TestRetryLimits:
    def test_retry_allowed_up_to_configured_maximum(self, db_session):
        cart, session_id, user_id = _cart_with_product(db_session)
        order = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart,
            discount_percent=0.0, payment_confirmed=True,
        )
        db_session.commit()

        provider = MockPaymentProvider()
        # MAX_PAYMENT_RETRIES defaults to 3 - all 3 attempts should be permitted.
        for _ in range(3):
            checkout_service.initiate_payment(db_session, order=order, provider=provider, simulated_outcome="FAILURE")
            db_session.commit()

        assert order.status == "RETRY_LIMIT_REACHED"

    def test_retry_blocked_after_limit_reached(self, db_session):
        cart, session_id, user_id = _cart_with_product(db_session)
        order = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart,
            discount_percent=0.0, payment_confirmed=True,
        )
        db_session.commit()

        provider = MockPaymentProvider()
        for _ in range(3):
            checkout_service.initiate_payment(db_session, order=order, provider=provider, simulated_outcome="FAILURE")
            db_session.commit()

        with pytest.raises(GuardrailViolation) as exc_info:
            checkout_service.request_retry(db_session, order=order)
        assert exc_info.value.rule == "INVALID_STATE_TRANSITION"

    def test_successful_payment_resets_retry_count(self, db_session):
        cart, session_id, user_id = _cart_with_product(db_session)
        order = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart,
            discount_percent=0.0, payment_confirmed=True,
        )
        db_session.commit()

        provider = MockPaymentProvider()
        checkout_service.initiate_payment(db_session, order=order, provider=provider, simulated_outcome="FAILURE")
        db_session.commit()
        assert order.retry_count == 1

        checkout_service.request_retry(db_session, order=order)
        db_session.commit()
        checkout_service.initiate_payment(db_session, order=order, provider=provider, simulated_outcome="SUCCESS")
        db_session.commit()

        assert order.status == "SUCCESS"
        assert order.retry_count == 0


class TestFailureRecovery:
    def test_failed_payment_does_not_mark_order_success(self, db_session):
        cart, session_id, user_id = _cart_with_product(db_session)
        order = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart,
            discount_percent=0.0, payment_confirmed=True,
        )
        db_session.commit()

        provider = MockPaymentProvider()
        checkout_service.initiate_payment(db_session, order=order, provider=provider, simulated_outcome="FAILURE")
        db_session.commit()

        assert order.status in {"RETRY_ALLOWED", "RETRY_LIMIT_REACHED"}
        assert order.status != "SUCCESS"

    def test_order_remains_recoverable_after_single_failure(self, db_session):
        cart, session_id, user_id = _cart_with_product(db_session)
        order = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart,
            discount_percent=0.0, payment_confirmed=True,
        )
        db_session.commit()

        provider = MockPaymentProvider()
        checkout_service.initiate_payment(db_session, order=order, provider=provider, simulated_outcome="FAILURE")
        db_session.commit()
        assert order.status == "RETRY_ALLOWED"

        checkout_service.request_retry(db_session, order=order)
        db_session.commit()
        assert order.status == "PAYMENT_PENDING"

        checkout_service.initiate_payment(db_session, order=order, provider=provider, simulated_outcome="SUCCESS")
        db_session.commit()
        assert order.status == "SUCCESS"

    def test_no_duplicate_charge_on_retry(self, db_session):
        """A retry after failure must reuse the SAME provider order id -
        never create a second Razorpay/mock order for the same checkout."""
        cart, session_id, user_id = _cart_with_product(db_session)
        order = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart,
            discount_percent=0.0, payment_confirmed=True,
        )
        db_session.commit()

        provider = MockPaymentProvider()
        checkout_service.initiate_payment(db_session, order=order, provider=provider, simulated_outcome="FAILURE")
        db_session.commit()
        first_provider_order_id = order.razorpay_order_id

        checkout_service.request_retry(db_session, order=order)
        db_session.commit()
        checkout_service.initiate_payment(db_session, order=order, provider=provider, simulated_outcome="SUCCESS")
        db_session.commit()

        assert order.razorpay_order_id == first_provider_order_id
