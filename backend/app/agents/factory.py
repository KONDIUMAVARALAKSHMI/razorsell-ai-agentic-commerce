from __future__ import annotations

from functools import lru_cache

from app.agents.ai_provider import AIProvider
from app.agents.mock_provider import MockAIProvider
from app.core.config import get_settings


@lru_cache
def get_ai_provider() -> AIProvider:
    settings = get_settings()
    if settings.AI_PROVIDER == "gemini":
        try:
            from app.agents.gemini_provider import GeminiAIProvider

            return GeminiAIProvider()
        except Exception:
            # Fail closed to the deterministic mock rather than breaking the
            # whole app if Gemini isn't configured correctly.
            return MockAIProvider()
    return MockAIProvider()
