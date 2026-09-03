from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/api/v1/merchant", tags=["merchant"])
settings = get_settings()

TOKEN_TTL_SECONDS = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


class LoginRequest(BaseModel):
    username: str
    password: str


def _sign(username: str, expiry: int) -> str:
    body = f"{username}:{expiry}"
    sig = hmac.new(settings.JWT_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}:{sig}"


def _verify(token: str) -> bool:
    try:
        username, expiry_str, sig = token.rsplit(":", 2)
        expiry = int(expiry_str)
    except (ValueError, AttributeError):
        return False
    if time.time() > expiry:
        return False
    expected = hmac.new(settings.JWT_SECRET.encode(), f"{username}:{expiry}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


@router.post("/login")
def login(payload: LoginRequest):
    """Demo-grade merchant auth: fixed credentials from environment
    variables, HMAC-signed opaque token. Not intended for production use -
    see docs/security.md 'Known limitations'."""
    if not (
        hmac.compare_digest(payload.username, settings.MERCHANT_DASHBOARD_USERNAME)
        and hmac.compare_digest(payload.password, settings.MERCHANT_DASHBOARD_PASSWORD)
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    expiry = int(time.time()) + TOKEN_TTL_SECONDS
    token = _sign(payload.username, expiry)
    return {"ok": True, "token": token, "expires_in": TOKEN_TTL_SECONDS}


def require_merchant_auth(authorization: str = Header(default="")) -> None:
    token = authorization.removeprefix("Bearer ").strip()
    if not token or not _verify(token):
        raise HTTPException(status_code=401, detail="Merchant authentication required.")
