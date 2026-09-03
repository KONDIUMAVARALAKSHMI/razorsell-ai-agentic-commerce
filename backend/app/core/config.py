"""
Central application configuration.

All secrets and environment-dependent values are read here, once, from
environment variables. Nothing in this file hardcodes a secret. See
.env.example at the repo root for the full list of supported variables.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


class Settings:
    # --- App ---
    APP_NAME: str = "RazorSell AI"
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = _get_bool("DEBUG", True)

    # --- Database ---
    # Defaults to a local SQLite file so the backend is runnable with zero
    # external services for quick evaluation. docker-compose overrides this
    # with a Postgres DSN.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./razorsell.db")

    # --- Redis (optional; falls back to in-memory if unavailable) ---
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    USE_REDIS: bool = _get_bool("USE_REDIS", False)

    # --- Auth ---
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-only-insecure-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = _get_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 12)
    MERCHANT_DASHBOARD_USERNAME: str = os.getenv("MERCHANT_DASHBOARD_USERNAME", "merchant")
    MERCHANT_DASHBOARD_PASSWORD: str = os.getenv("MERCHANT_DASHBOARD_PASSWORD", "demo-password")

    # --- CORS ---
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

    # --- AI provider ---
    AI_PROVIDER: Literal["gemini", "mock"] = os.getenv("AI_PROVIDER", "mock")  # type: ignore
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # --- Payment provider ---
    PAYMENT_PROVIDER: Literal["razorpay", "mock"] = os.getenv("PAYMENT_PROVIDER", "mock")  # type: ignore
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # --- Business rules (deterministic policy, never controlled by the AI) ---
    MAX_UPSELL_RECOMMENDATIONS: int = _get_int("MAX_UPSELL_RECOMMENDATIONS", 2)
    MAX_PAYMENT_RETRIES: int = _get_int("MAX_PAYMENT_RETRIES", 3)
    RETRY_COOLDOWN_SECONDS: int = _get_int("RETRY_COOLDOWN_SECONDS", 5)
    MAX_DISCOUNT_PERCENT: float = float(os.getenv("MAX_DISCOUNT_PERCENT", "5.0"))

    # --- Rate limiting ---
    # A single customer journey (search -> select -> upsell -> cart ->
    # checkout -> payment -> retry) is easily 8-10 requests; 300/minute per
    # IP comfortably covers a live demo with several reviewers on the same
    # network without materially weakening abuse protection for a hackathon
    # deployment. Automated batch traffic (the evaluation harness) overrides
    # this via the RATE_LIMIT_PER_MINUTE environment variable.
    RATE_LIMIT_PER_MINUTE: int = _get_int("RATE_LIMIT_PER_MINUTE", 300)


@lru_cache
def get_settings() -> Settings:
    return Settings()
