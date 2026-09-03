from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("PAYMENT_PROVIDER", "mock")

from app.core import db as db_module  # noqa: E402
from app.core.db import Base  # noqa: E402


@pytest.fixture()
def db_session():
    """A fresh in-memory SQLite database per test, with the app's engine
    and session factory monkeypatched to point at it so every service
    function under test uses the same isolated DB."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    import app.models  # noqa: F401 - register all tables

    Base.metadata.create_all(bind=engine)

    db_module.engine = engine
    db_module.SessionLocal = TestingSessionLocal

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    """A TestClient wired to use the SAME in-memory DB session as db_session,
    via a FastAPI dependency override."""
    from app.core.db import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_client(client, db_session):
    """Client with the standard demo catalog seeded into the isolated DB."""
    from scripts.seed_database import ACCESSORIES, GAMING, LAPTOPS, RELATIONS, _upsert_product
    from app.models.catalog import Product, ProductRelation
    from app.models.users import Merchant

    by_sku: dict[str, Product] = {}
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
    return client


def new_session_id() -> str:
    return str(uuid.uuid4())


def new_user_id() -> str:
    return str(uuid.uuid4())
