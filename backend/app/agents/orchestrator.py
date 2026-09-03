"""
The orchestrator is intentionally NOT a free-form autonomous agent loop.
It is a bounded state machine: at each turn it uses the AI provider ONLY for
(a) understanding the customer's message and (b) writing a short, grounded
explanation of what the deterministic layer already decided. It never lets
the model choose arbitrary tools with arbitrary arguments against the
payment or pricing systems - see docs/security.md for the full rationale.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.ai_provider import AIProvider
from app.audit.service import record_event
from app.models.agent import AgentMessage, AgentSession, Recommendation
from app.models.catalog import Product
from app.services.cart import add_to_cart, get_cart_snapshot, get_or_create_cart
from app.services.catalog import search_products
from app.services.upsell import get_upsell_candidates


def get_or_create_agent_session(db: Session, *, session_id: str, user_id: str) -> AgentSession:
    session = db.get(AgentSession, session_id)
    if session is None:
        session = AgentSession(id=session_id, user_id=user_id)
        db.add(session)
        db.flush()
    return session


def handle_customer_message(
    db: Session,
    *,
    ai: AIProvider,
    session_id: str,
    user_id: str,
    message: str,
) -> dict:
    """The main chat turn. Returns a JSON-serializable payload the frontend
    renders directly: understood intent, ranked product cards (grounded in
    the DB), and a short natural-language reply."""
    agent_session = get_or_create_agent_session(db, session_id=session_id, user_id=user_id)

    db.add(AgentMessage(session_id=agent_session.id, role="user", content=message))
    record_event(
        db,
        session_id=session_id,
        event_type="USER_MESSAGE",
        actor="USER",
        action="Customer sent a chat message.",
        user_id=user_id,
        metadata={"length": len(message)},
    )

    intent = ai.extract_intent(message)
    agent_session.last_intent = {
        "category": intent.category,
        "budget_max": intent.budget_max,
        "use_cases": intent.use_cases,
        "priority": intent.priority,
    }
    db.flush()

    record_event(
        db,
        session_id=session_id,
        event_type="AI_DECISION",
        actor="AI",
        action="Extracted shopping intent from customer message.",
        user_id=user_id,
        metadata=agent_session.last_intent,
    )

    record_event(
        db,
        session_id=session_id,
        event_type="PRODUCT_SEARCH",
        actor="SYSTEM",
        action="Searched catalog using deterministic scoring.",
        user_id=user_id,
        metadata=agent_session.last_intent,
    )
    ranked = search_products(db, intent, limit=5)

    if not ranked:
        reply = ai.conversational_reply(context={"stage": "no_results"})
        db.add(AgentMessage(session_id=agent_session.id, role="assistant", content=reply))
        return {
            "understood_intent": intent.raw_summary,
            "reply": reply,
            "products": [],
        }

    product_cards = []
    for scored in ranked:
        explanation = ai.explain_recommendation(product_name=scored.product.name, reasons=scored.reasons)
        db.add(
            Recommendation(
                session_id=agent_session.id,
                product_id=scored.product.id,
                kind="primary",
                score=scored.score,
                reason=explanation,
            )
        )
        product_cards.append(
            {
                "product_id": scored.product.id,
                "name": scored.product.name,
                "price": scored.product.price,
                "category": scored.product.category,
                "score": scored.score,
                "why_this_product": explanation,
            }
        )

    record_event(
        db,
        session_id=session_id,
        event_type="PRODUCT_RECOMMENDATION",
        actor="AI",
        action=f"Recommended {len(product_cards)} grounded product(s).",
        user_id=user_id,
        metadata={"product_ids": [c["product_id"] for c in product_cards]},
    )

    reply = ai.conversational_reply(context={"stage": "results", "count": len(product_cards)})
    db.add(AgentMessage(session_id=agent_session.id, role="assistant", content=reply))
    db.flush()

    return {
        "understood_intent": intent.raw_summary,
        "reply": reply,
        "products": product_cards,
    }


def select_product(
    db: Session,
    *,
    ai: AIProvider,
    session_id: str,
    user_id: str,
    product_id: str,
) -> dict:
    """Customer picks a product -> add to cart -> surface bounded upsell."""
    cart = get_or_create_cart(db, session_id=session_id, user_id=user_id)
    add_to_cart(db, cart=cart, product_id=product_id, quantity=1, added_via="user")

    record_event(
        db,
        session_id=session_id,
        event_type="CART_UPDATED",
        actor="USER",
        action="Customer added the recommended product to the cart.",
        user_id=user_id,
        metadata={"product_id": product_id},
    )

    agent_session = get_or_create_agent_session(db, session_id=session_id, user_id=user_id)
    candidates = get_upsell_candidates(db, product_id=product_id, already_shown=agent_session.upsell_count)

    primary_product = db.get(Product, product_id)
    upsell_cards = []
    for candidate in candidates:
        explanation = ai.explain_upsell(
            product_name=candidate.product.name,
            primary_product_name=primary_product.name if primary_product else "your selection",
            reason=candidate.reason,
        )
        db.add(
            Recommendation(
                session_id=agent_session.id,
                product_id=candidate.product.id,
                kind=candidate.relation_type,
                score=0.0,
                reason=explanation,
            )
        )
        upsell_cards.append(
            {
                "product_id": candidate.product.id,
                "name": candidate.product.name,
                "price": candidate.product.price,
                "why_recommended": explanation,
                "bundle_discount_percent": candidate.bundle_discount_percent,
            }
        )
        agent_session.upsell_count += 1
        record_event(
            db,
            session_id=session_id,
            event_type="UPSELL_RECOMMENDATION",
            actor="AI",
            action=f"Recommended complementary product: {candidate.product.name}.",
            user_id=user_id,
            metadata={"product_id": candidate.product.id, "relation_type": candidate.relation_type},
        )

    db.flush()
    snapshot = get_cart_snapshot(db, cart=cart)
    return {"cart": snapshot, "upsell": upsell_cards}
