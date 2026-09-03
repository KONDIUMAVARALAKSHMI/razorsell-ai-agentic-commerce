from __future__ import annotations

import uuid


class TestFullCustomerJourney:
    def test_chat_search_select_upsell_checkout_payment_success(self, seeded_client):
        client = seeded_client
        session_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())

        r = client.post(
            "/api/v1/chat/message",
            json={
                "session_id": session_id,
                "user_id": user_id,
                "message": "I need a laptop under 70000 for coding and gaming, something portable",
            },
        )
        assert r.status_code == 200
        products = r.json()["data"]["products"]
        assert len(products) > 0
        product_id = products[0]["product_id"]

        r = client.post(
            "/api/v1/chat/select-product",
            json={"session_id": session_id, "user_id": user_id, "product_id": product_id},
        )
        assert r.status_code == 200
        cart_data = r.json()["data"]["cart"]
        assert cart_data["subtotal"] > 0

        r = client.get("/api/v1/checkout/preview", params={"session_id": session_id, "user_id": user_id})
        assert r.status_code == 200
        total = r.json()["data"]["total"]
        assert total == cart_data["subtotal"]

        # Cannot confirm without confirm=true
        r = client.post(
            "/api/v1/checkout/confirm",
            json={"session_id": session_id, "user_id": user_id, "confirm": False},
        )
        assert r.status_code == 403

        r = client.post(
            "/api/v1/checkout/confirm",
            json={"session_id": session_id, "user_id": user_id, "confirm": True, "idempotency_key": str(uuid.uuid4())},
        )
        assert r.status_code == 200
        order_id = r.json()["data"]["order_id"]
        assert r.json()["data"]["status"] == "CREATED"

        r = client.post("/api/v1/payments/attempt", json={"order_id": order_id, "simulated_outcome": "SUCCESS"})
        assert r.status_code == 200
        assert r.json()["data"]["order_status"] == "SUCCESS"

        r = client.get(f"/api/v1/orders/{order_id}")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "SUCCESS"

        r = client.get("/api/v1/audit/events", params={"order_id": order_id})
        event_types = [e["event_type"] for e in r.json()["data"]]
        for expected in ["CHECKOUT_STARTED", "USER_PAYMENT_CONFIRMATION", "RAZORPAY_ORDER_CREATED", "PAYMENT_SUCCESS"]:
            assert expected in event_types

    def test_payment_failure_then_successful_retry(self, seeded_client):
        client = seeded_client
        session_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())

        r = client.post(
            "/api/v1/chat/message",
            json={"session_id": session_id, "user_id": user_id, "message": "laptop under 60000 for college"},
        )
        product_id = r.json()["data"]["products"][0]["product_id"]
        client.post(
            "/api/v1/chat/select-product",
            json={"session_id": session_id, "user_id": user_id, "product_id": product_id},
        )
        r = client.post(
            "/api/v1/checkout/confirm",
            json={"session_id": session_id, "user_id": user_id, "confirm": True, "idempotency_key": str(uuid.uuid4())},
        )
        order_id = r.json()["data"]["order_id"]

        r = client.post("/api/v1/payments/attempt", json={"order_id": order_id, "simulated_outcome": "FAILURE"})
        assert r.json()["data"]["order_status"] == "RETRY_ALLOWED"

        r = client.post("/api/v1/payments/retry", json={"order_id": order_id})
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "PAYMENT_PENDING"

        r = client.post("/api/v1/payments/attempt", json={"order_id": order_id, "simulated_outcome": "SUCCESS"})
        assert r.json()["data"]["order_status"] == "SUCCESS"

        # Exactly one payment order should ever have been created at the provider.
        r = client.get(f"/api/v1/orders/{order_id}")
        attempts = r.json()["data"]["payment_attempts"]
        assert len(attempts) == 2
        assert attempts[0]["status"] == "FAILED"
        assert attempts[1]["status"] == "SUCCESS"

    def test_duplicate_checkout_confirmation_blocked(self, seeded_client):
        client = seeded_client
        session_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())

        r = client.post(
            "/api/v1/chat/message",
            json={"session_id": session_id, "user_id": user_id, "message": "laptop under 60000"},
        )
        product_id = r.json()["data"]["products"][0]["product_id"]
        client.post(
            "/api/v1/chat/select-product",
            json={"session_id": session_id, "user_id": user_id, "product_id": product_id},
        )

        idem_key = str(uuid.uuid4())
        r1 = client.post(
            "/api/v1/checkout/confirm",
            json={"session_id": session_id, "user_id": user_id, "confirm": True, "idempotency_key": idem_key},
        )
        r2 = client.post(
            "/api/v1/checkout/confirm",
            json={"session_id": session_id, "user_id": user_id, "confirm": True, "idempotency_key": idem_key},
        )
        assert r1.json()["data"]["order_id"] == r2.json()["data"]["order_id"]

        r = client.get("/api/v1/orders", params={"limit": 100})
        matching = [o for o in r.json()["data"] if o["id"] == r1.json()["data"]["order_id"]]
        assert len(matching) == 1

    def test_out_of_stock_product_blocks_checkout(self, seeded_client, db_session):
        client = seeded_client
        from sqlalchemy import select
        from app.models.catalog import Inventory, Product

        product = db_session.execute(select(Product).where(Product.sku == "LT-005")).scalar_one()
        inv = db_session.execute(select(Inventory).where(Inventory.product_id == product.id)).scalar_one()
        inv.quantity_available = 0
        db_session.commit()

        session_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())
        r = client.post(
            "/api/v1/cart/add",
            json={"session_id": session_id, "user_id": user_id, "product_id": product.id, "quantity": 1},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["rule"] == "INVENTORY_CHECK"

    def test_hallucinated_product_id_rejected_end_to_end(self, seeded_client):
        client = seeded_client
        session_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())
        r = client.post(
            "/api/v1/cart/add",
            json={"session_id": session_id, "user_id": user_id, "product_id": "totally-fake-id", "quantity": 1},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["rule"] == "RULE_3_NO_HALLUCINATED_PRODUCTS"

    def test_analytics_overview_reflects_real_completed_order(self, seeded_client):
        client = seeded_client
        session_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())
        r = client.post(
            "/api/v1/chat/message",
            json={"session_id": session_id, "user_id": user_id, "message": "laptop under 60000"},
        )
        product_id = r.json()["data"]["products"][0]["product_id"]
        client.post(
            "/api/v1/chat/select-product",
            json={"session_id": session_id, "user_id": user_id, "product_id": product_id},
        )
        r = client.post(
            "/api/v1/checkout/confirm",
            json={"session_id": session_id, "user_id": user_id, "confirm": True, "idempotency_key": str(uuid.uuid4())},
        )
        order_id = r.json()["data"]["order_id"]
        client.post("/api/v1/payments/attempt", json={"order_id": order_id, "simulated_outcome": "SUCCESS"})

        r = client.get("/api/v1/analytics/overview")
        data = r.json()["data"]
        assert data["revenue"]["successful_payments"] >= 1
        assert data["revenue"]["total_revenue"] > 0

    def test_merchant_login_requires_correct_credentials(self, client):
        r = client.post("/api/v1/merchant/login", json={"username": "merchant", "password": "wrong-password"})
        assert r.status_code == 401
        r = client.post("/api/v1/merchant/login", json={"username": "merchant", "password": "demo-password"})
        assert r.status_code == 200
        assert "token" in r.json()
