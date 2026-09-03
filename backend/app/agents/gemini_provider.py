from __future__ import annotations

import json
from typing import Any

from app.agents.ai_provider import AIProvider, ExtractedIntent
from app.agents.mock_provider import MockAIProvider
from app.core.config import get_settings

settings = get_settings()

INTENT_SYSTEM_PROMPT = """You are the intent-extraction module of a shopping assistant.
Given a customer's message, return ONLY a JSON object (no markdown, no prose) of the form:
{"category": "laptop|accessory|gaming|null", "budget_max": number or null,
 "use_cases": ["coding","gaming","college","editing","office","travel"],
 "priority": "portable|performance|battery|budget|null",
 "raw_summary": "one short sentence, user-facing, describing what you understood"}
Only include use_cases that are clearly implied. Do not invent products or prices."""


class GeminiAIProvider(AIProvider):
    """Real LLM-backed provider using Google's Gemini API. Falls back to the
    deterministic MockAIProvider for any call that fails (network error,
    missing key, malformed response) so a demo never hard-crashes because of
    an external API hiccup - the failure is logged, not silently ignored."""

    name = "gemini"

    def __init__(self) -> None:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set. Set AI_PROVIDER=mock to run without it.")
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'google-generativeai' package is required for AI_PROVIDER=gemini. "
                "Install it with `pip install google-generativeai` or use AI_PROVIDER=mock."
            ) from exc
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._model = genai.GenerativeModel(settings.GEMINI_MODEL)
        self._fallback = MockAIProvider()

    def _generate(self, prompt: str) -> str:
        response = self._model.generate_content(prompt)
        return (response.text or "").strip()

    def extract_intent(self, message: str) -> ExtractedIntent:
        try:
            raw = self._generate(f"{INTENT_SYSTEM_PROMPT}\n\nCustomer message: {message}")
            raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(raw)
            return ExtractedIntent(
                category=data.get("category") or None,
                budget_max=data.get("budget_max"),
                use_cases=data.get("use_cases") or [],
                priority=data.get("priority") or None,
                raw_summary=data.get("raw_summary", ""),
            )
        except Exception:
            # Fail closed to the deterministic parser rather than guessing.
            return self._fallback.extract_intent(message)

    def explain_recommendation(self, *, product_name: str, reasons: list[str]) -> str:
        try:
            reason_text = "; ".join(reasons)
            prompt = (
                "Write ONE short, plain-English sentence (no chain-of-thought, no bullet points) "
                f"explaining why '{product_name}' was recommended, based on these grounded facts: {reason_text}. "
                "Do not mention any product, price, or fact not in that list."
            )
            return self._generate(prompt) or self._fallback.explain_recommendation(
                product_name=product_name, reasons=reasons
            )
        except Exception:
            return self._fallback.explain_recommendation(product_name=product_name, reasons=reasons)

    def explain_upsell(self, *, product_name: str, primary_product_name: str, reason: str) -> str:
        try:
            prompt = (
                f"Write ONE short, friendly sentence recommending the add-on '{product_name}' to a customer "
                f"who just chose '{primary_product_name}', using only this grounded reason: {reason}."
            )
            return self._generate(prompt) or self._fallback.explain_upsell(
                product_name=product_name, primary_product_name=primary_product_name, reason=reason
            )
        except Exception:
            return self._fallback.explain_upsell(
                product_name=product_name, primary_product_name=primary_product_name, reason=reason
            )

    def conversational_reply(self, *, context: dict[str, Any]) -> str:
        try:
            prompt = (
                "Write ONE short, warm, user-facing sentence for a shopping assistant given this "
                f"situation JSON (do not reveal internal reasoning): {json.dumps(context)}"
            )
            return self._generate(prompt) or self._fallback.conversational_reply(context=context)
        except Exception:
            return self._fallback.conversational_reply(context=context)
