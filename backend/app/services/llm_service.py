"""
LLM service for DeepSeek integration via OpenRouter
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Service wrapper around LLM providers."""

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the underlying LLM client."""
        if self._initialized:
            return

        provider = settings.LLM_PROVIDER.lower()

        if provider == "openrouter":
            if not settings.OPENROUTER_API_KEY:
                logger.warning("OpenRouter API key missing; LLM disabled.")
                return

            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.OPENROUTER_API_KEY,
            )
            self._initialized = True
            logger.info("LLM service initialized with OpenRouter (DeepSeek).")
            return

        logger.info("LLM provider set to 'none'; LLM integration disabled.")

    async def generate_summary(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """Generate a summary using the configured LLM provider."""
        if not self._client:
            raise RuntimeError("LLM client not initialized.")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a location intelligence analyst. Generate comprehensive, "
                    "data-driven summaries about geographic locations. Be objective, "
                    "factual, and helpful for people evaluating the area."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]

        logger.debug("Submitting prompt to LLM provider.")

        def _invoke_llm() -> str:
            response = self._client.chat.completions.create(
                model=settings.LLM_MODEL or "deepseek/deepseek-chat:free",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()

        return await asyncio.to_thread(_invoke_llm)


# Shared service instance
llm_service = LLMService()



