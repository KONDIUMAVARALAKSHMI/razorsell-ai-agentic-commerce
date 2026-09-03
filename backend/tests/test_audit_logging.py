from __future__ import annotations

from sqlalchemy import select

from app.models.audit import AuditEvent
from app.payments.mock_provider import MockPaymentProvider
from app.services import cart as cart_service
from app.services import checkout as checkout_service
from tests.conftest import new_session_id, new_user_id


def _seed_one_product(db_session):
    from scripts.seed_database import LAPTOPS, _upsert_product

    return _upsert_product(db_session, LAPTOPS[0], "laptop")


class TestAuditLogging:
    def test_checkout_started_and_confirmation_events_recorded(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()
        session_id, user_id = new_session_id(), new_user_id()
        cart = cart_service.get_or_create_cart(db_session, session_id=session_id, user_id=user_id)
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()

        order = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart,
            discount_percent=0.0, payment_confirmed=True,
        )
        db_session.commit()

        events = db_session.execute(
            select(AuditEvent).where(AuditEvent.order_id == order.id)
        ).scalars().all()
        event_types = {e.event_type for e in events}
        assert "CHECKOUT_STARTED" in event_types
        assert "USER_PAYMENT_CONFIRMATION" in event_types

    def test_every_payment_attempt_produces_an_audit_event(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()
        session_id, user_id = new_session_id(), new_user_id()
        cart = cart_service.get_or_create_cart(db_session, session_id=session_id, user_id=user_id)
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()
        order = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart,
            discount_percent=0.0, payment_confirmed=True,
        )
        db_session.commit()

        provider = MockPaymentProvider()
        checkout_service.initiate_payment(db_session, order=order, provider=provider, simulated_outcome="SUCCESS")
        db_session.commit()

        events = db_session.execute(
            select(AuditEvent).where(AuditEvent.order_id == order.id, AuditEvent.event_type == "PAYMENT_ATTEMPTED")
        ).scalars().all()
        assert len(events) == 1

        success_events = db_session.execute(
            select(AuditEvent).where(AuditEvent.order_id == order.id, AuditEvent.event_type == "PAYMENT_SUCCESS")
        ).scalars().all()
        assert len(success_events) == 1

    def test_blocked_action_produces_guardrail_blocked_event(self, db_session):
        product = _seed_one_product(db_session)
        db_session.commit()
        session_id, user_id = new_session_id(), new_user_id()
        cart = cart_service.get_or_create_cart(db_session, session_id=session_id, user_id=user_id)
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()

        try:
            checkout_service.create_order(
                db_session, session_id=session_id, user_id=user_id, cart=cart,
                discount_percent=0.0, payment_confirmed=False,
            )
        except Exception:
            pass

        events = db_session.execute(
            select(AuditEvent).where(AuditEvent.session_id == session_id, AuditEvent.event_type == "GUARDRAIL_BLOCKED")
        ).scalars().all()
        assert len(events) == 1
        assert events[0].status == "BLOCKED"

    def test_no_secrets_ever_appear_in_audit_metadata(self, db_session):
        """Sanity check: audit metadata for a payment attempt must never
        contain the word 'secret' or 'key_secret' - only IDs and statuses."""
        product = _seed_one_product(db_session)
        db_session.commit()
        session_id, user_id = new_session_id(), new_user_id()
        cart = cart_service.get_or_create_cart(db_session, session_id=session_id, user_id=user_id)
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()
        order = checkout_service.create_order(
            db_session, session_id=session_id, user_id=user_id, cart=cart,
            discount_percent=0.0, payment_confirmed=True,
        )
        db_session.commit()
        provider = MockPaymentProvider()
        checkout_service.initiate_payment(db_session, order=order, provider=provider, simulated_outcome="SUCCESS")
        db_session.commit()

        events = db_session.execute(select(AuditEvent)).scalars().all()
        for e in events:
            serialized = str(e.event_metadata).lower()
            assert "secret" not in serialized
            assert "razorpay_key_secret" not in serialized
