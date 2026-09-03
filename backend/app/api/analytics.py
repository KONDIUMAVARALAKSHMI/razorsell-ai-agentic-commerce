from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import guarded
from app.core.db import get_db
from app.models.agent import AgentSession, Recommendation
from app.models.audit import AuditEvent
from app.models.orders import Order, PaymentAttempt
from app.schemas.api import GenericResponse

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/overview", response_model=GenericResponse)
def overview(db: Session = Depends(get_db)):
    with guarded():
        total_orders = db.execute(select(func.count(Order.id))).scalar_one()
        successful = db.execute(select(func.count(Order.id)).where(Order.status == "SUCCESS")).scalar_one()
        total_revenue = db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0.0)).where(Order.status == "SUCCESS")
        ).scalar_one()
        conversion_rate = (successful / total_orders * 100.0) if total_orders else 0.0
        aov = (total_revenue / successful) if successful else 0.0

        upsell_recs = db.execute(
            select(Recommendation).where(Recommendation.kind.in_(["upsell", "cross_sell"]))
        ).scalars().all()
        upsell_shown = len(upsell_recs)
        upsell_accepted = len([r for r in upsell_recs if r.accepted is True])
        upsell_rate = (upsell_accepted / upsell_shown * 100.0) if upsell_shown else 0.0

        # Incremental revenue = revenue from order items whose CartItem was added_via upsell_accept,
        # approximated here via successful orders' item-level data is not tracked per-source at the
        # order_item level in this schema, so we report upsell items accepted * their price as a proxy.
        from app.models.catalog import Product

        incremental_revenue = 0.0
        for rec in upsell_recs:
            if rec.accepted:
                product = db.get(Product, rec.product_id)
                if product:
                    incremental_revenue += product.price

        payment_failures = db.execute(
            select(func.count(PaymentAttempt.id)).where(PaymentAttempt.status == "FAILED")
        ).scalar_one()
        successful_recoveries = db.execute(
            select(func.count(AuditEvent.event_id)).where(AuditEvent.event_type == "PAYMENT_SUCCESS")
        ).scalar_one()
        duplicate_blocked = db.execute(
            select(func.count(AuditEvent.event_id)).where(AuditEvent.event_type == "DUPLICATE_REQUEST_BLOCKED")
        ).scalar_one()
        blocked_unsafe = db.execute(
            select(func.count(AuditEvent.event_id)).where(AuditEvent.event_type == "GUARDRAIL_BLOCKED")
        ).scalar_one()

        conversations = db.execute(select(func.count(AgentSession.id))).scalar_one()
        product_searches = db.execute(
            select(func.count(AuditEvent.event_id)).where(AuditEvent.event_type == "PRODUCT_SEARCH")
        ).scalar_one()

        avg_retry = db.execute(select(func.coalesce(func.avg(Order.retry_count), 0.0))).scalar_one()

        return GenericResponse(
            ok=True,
            data={
                "revenue": {
                    "total_orders": total_orders,
                    "successful_payments": successful,
                    "conversion_rate_percent": round(conversion_rate, 2),
                    "total_revenue": round(total_revenue, 2),
                    "average_order_value": round(aov, 2),
                    "upsell_acceptance_rate_percent": round(upsell_rate, 2),
                    "incremental_upsell_revenue": round(incremental_revenue, 2),
                },
                "agent": {
                    "conversations": conversations,
                    "product_searches": product_searches,
                    "recommendations_shown": upsell_shown,
                    "blocked_unsafe_actions": blocked_unsafe,
                },
                "reliability": {
                    "payment_failures": payment_failures,
                    "successful_payments": successful_recoveries,
                    "duplicate_requests_blocked": duplicate_blocked,
                    "average_retry_count": round(float(avg_retry), 2),
                },
            },
        )
