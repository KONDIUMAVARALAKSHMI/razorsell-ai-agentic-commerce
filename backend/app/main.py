from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import analytics, audit, cart, catalog, chat, checkout, merchant, orders, payments
from app.core.config import get_settings
from app.core.db import Base, engine

settings = get_settings()

app = FastAPI(
    title="RazorSell AI",
    description="AI Merchant Sales & Agentic Checkout Platform (Razorpay Test Mode only).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Minimal in-memory rate limiter (per client IP, sliding window) ---
# For a single-process demo this is sufficient; a multi-process deployment
# would back this with Redis instead (see app/core/config.py USE_REDIS).
_request_log: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = _request_log[client_ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= settings.RATE_LIMIT_PER_MINUTE:
        return JSONResponse(status_code=429, content={"ok": False, "error": "Rate limit exceeded."})
    window.append(now)
    return await call_next(request)


@app.on_event("startup")
def on_startup() -> None:
    # Creates tables if they don't exist yet. Alembic migrations
    # (backend/alembic) are the source of truth for schema evolution;
    # this call is a convenience for local/demo runs and CI.
    import app.models  # noqa: F401 - ensures all models are registered on Base.metadata

    Base.metadata.create_all(bind=engine)


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "ai_provider": settings.AI_PROVIDER, "payment_provider": settings.PAYMENT_PROVIDER}


app.include_router(catalog.router)
app.include_router(chat.router)
app.include_router(cart.router)
app.include_router(checkout.router)
app.include_router(payments.router)
app.include_router(orders.router)
app.include_router(audit.router)
app.include_router(analytics.router)
app.include_router(merchant.router)
