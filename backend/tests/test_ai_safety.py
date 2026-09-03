from __future__ import annotations

import pytest

from app.agents.ai_provider import ExtractedIntent
from app.guardrails.policy import GuardrailViolation
from app.services import cart as cart_service
from app.services import catalog as catalog_service
from app.services import checkout as checkout_service
from app.services import upsell as upsell_service
from tests.conftest import new_session_id, new_user_id


def _seed_full_catalog(db_session):
    from scripts.seed_database import ACCESSORIES, GAMING, LAPTOPS, RELATIONS, _upsert_product
    from app.models.catalog import ProductRelation

    by_sku = {}
    for item in LAPTOPS:
        by_sku[item["sku"]] = _upsert_product(db_session, item, "laptop")
    for item in ACCESSORIES:
        by_sku[item["sku"]] = _upsert_product(db_session, item, "accessory")
    for item in GAMING:
        by_sku[item["sku"]] = _upsert_product(db_session, item, "gaming")
    for sku, related_sku, relation_type, reason, discount in RELATIONS:
        db_session.add(
            ProductRelation(
                product_id=by_sku[sku].id,
                related_product_id=by_sku[related_sku].id,
                relation_type=relation_type,
                reason=reason,
                bundle_discount_percent=discount,
            )
        )
    db_session.commit()
    return by_sku


class TestProductHallucinationPrevention:
    def test_search_never_returns_a_product_not_in_the_database(self, db_session):
        by_sku = _seed_full_catalog(db_session)
        intent = ExtractedIntent(category="laptop", budget_max=70000, use_cases=["coding", "gaming"], priority="portable")
        results = catalog_service.search_products(db_session, intent, limit=10)
        real_ids = {p.id for p in by_sku.values()}
        for scored in results:
            assert scored.product.id in real_ids

    def test_cannot_add_a_fabricated_product_id_to_cart(self, db_session):
        cart = cart_service.get_or_create_cart(db_session, session_id=new_session_id(), user_id=new_user_id())
        with pytest.raises(GuardrailViolation) as exc_info:
            cart_service.add_to_cart(db_session, cart=cart, product_id="fake-product-id-12345", quantity=1)
        assert exc_info.value.rule == "RULE_3_NO_HALLUCINATED_PRODUCTS"

    def test_compare_silently_drops_nonexistent_ids_rather_than_fabricating(self, db_session):
        by_sku = _seed_full_catalog(db_session)
        real_id = by_sku["LT-001"].id
        results = catalog_service.compare_products(db_session, [real_id, "does-not-exist"])
        assert len(results) == 1
        assert results[0].id == real_id


class TestPriceIntegrity:
    def test_ai_cannot_influence_order_total_price_comes_from_db(self, db_session):
        by_sku = _seed_full_catalog(db_session)
        product = by_sku["LT-001"]
        session_id, user_id = new_session_id(), new_user_id()
        cart = cart_service.get_or_create_cart(db_session, session_id=session_id, user_id=user_id)
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()

        # calculate_checkout has no parameter for an AI-suggested price at all -
        # it is architecturally impossible to pass one in.
        totals = checkout_service.calculate_checkout(db_session, cart=cart, discount_percent=0.0)
        assert totals.subtotal == product.price

    def test_unauthorized_discount_beyond_ceiling_is_rejected(self, db_session):
        by_sku = _seed_full_catalog(db_session)
        product = by_sku["LT-001"]
        session_id, user_id = new_session_id(), new_user_id()
        cart = cart_service.get_or_create_cart(db_session, session_id=session_id, user_id=user_id)
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()

        with pytest.raises(GuardrailViolation) as exc_info:
            checkout_service.calculate_checkout(db_session, cart=cart, discount_percent=40.0)
        assert exc_info.value.rule == "RULE_2_DISCOUNT_BOUNDS"


class TestPaymentConfirmationBypass:
    def test_payment_cannot_be_created_without_explicit_confirmation(self, db_session):
        by_sku = _seed_full_catalog(db_session)
        product = by_sku["LT-001"]
        session_id, user_id = new_session_id(), new_user_id()
        cart = cart_service.get_or_create_cart(db_session, session_id=session_id, user_id=user_id)
        cart_service.add_to_cart(db_session, cart=cart, product_id=product.id, quantity=1)
        db_session.commit()

        with pytest.raises(GuardrailViolation) as exc_info:
            checkout_service.create_order(
                db_session, session_id=session_id, user_id=user_id, cart=cart,
                discount_percent=0.0, payment_confirmed=False,
            )
        assert exc_info.value.rule == "RULE_1_EXPLICIT_CONFIRMATION"
        # And crucially: no order row should exist as a side effect.
        from sqlalchemy import select
        from app.models.orders import Order

        orders = db_session.execute(select(Order).where(Order.session_id == session_id)).scalars().all()
        assert orders == []


class TestUpsellGuardrails:
    def test_upsell_candidates_only_come_from_curated_relations(self, db_session):
        by_sku = _seed_full_catalog(db_session)
        laptop = by_sku["LT-003"]  # has curated relations to AC-001 and GM-006
        candidates = upsell_service.get_upsell_candidates(db_session, product_id=laptop.id, already_shown=0)
        allowed_related_ids = {by_sku["AC-001"].id, by_sku["GM-006"].id}
        for c in candidates:
            assert c.product.id in allowed_related_ids

    def test_upsell_never_recommends_an_unrelated_product(self, db_session):
        by_sku = _seed_full_catalog(db_session)
        # AC-002 has no curated relations defined FROM it in our seed data
        # (relations only run laptop -> accessory/gaming), so it must yield nothing.
        accessory = by_sku["AC-002"]
        candidates = upsell_service.get_upsell_candidates(db_session, product_id=accessory.id, already_shown=0)
        assert candidates == []

    def test_max_two_upsells_enforced_across_calls(self, db_session):
        by_sku = _seed_full_catalog(db_session)
        laptop = by_sku["LT-003"]
        first_batch = upsell_service.get_upsell_candidates(db_session, product_id=laptop.id, already_shown=0)
        assert len(first_batch) <= 2
        second_batch = upsell_service.get_upsell_candidates(db_session, product_id=laptop.id, already_shown=2)
        assert second_batch == []

    def test_out_of_stock_upsell_candidate_is_excluded(self, db_session):
        by_sku = _seed_full_catalog(db_session)
        laptop = by_sku["LT-003"]
        mouse = by_sku["AC-001"]
        # Deplete inventory for the mouse.
        mouse.inventory.quantity_available = 0
        db_session.commit()

        candidates = upsell_service.get_upsell_candidates(db_session, product_id=laptop.id, already_shown=0)
        candidate_ids = {c.product.id for c in candidates}
        assert mouse.id not in candidate_ids

    def test_out_of_stock_product_excluded_from_search_recommendations(self, db_session):
        by_sku = _seed_full_catalog(db_session)
        laptop = by_sku["LT-001"]
        laptop.inventory.quantity_available = 0
        db_session.commit()

        intent = ExtractedIntent(category="laptop", budget_max=100000, use_cases=[], priority=None)
        results = catalog_service.search_products(db_session, intent, limit=20)
        result_ids = {s.product.id for s in results}
        assert laptop.id not in result_ids
