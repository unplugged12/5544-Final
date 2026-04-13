"""Anthropic provider implementation using AsyncAnthropic."""

import logging

from anthropic import AsyncAnthropic

from config import settings
from providers.base import BaseLLMProvider, ProviderResponse
from providers.utils import format_chunks

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._model = settings.ANTHROPIC_MODEL

    # ------------------------------------------------------------------
    async def generate_grounded_answer(
        self,
        query: str,
        context_chunks: list[dict],
        system_prompt: str,
    ) -> ProviderResponse:
        context_block = format_chunks(context_chunks)

        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Context:\n{context_block}\n\nQuestion: {query}",
                }
            ],
            temperature=0.3,
        )

        return ProviderResponse(
            text=resp.content[0].text,
            provider_name="anthropic",
            model=self._model,
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        )

    # ------------------------------------------------------------------
    async def generate_summary(
        self,
        text: str,
        system_prompt: str,
    ) -> ProviderResponse:
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"Summarize this:\n\n{text}"}
            ],
            temperature=0.3,
        )

        return ProviderResponse(
            text=resp.content[0].text,
            provider_name="anthropic",
            model=self._model,
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        )

    # ------------------------------------------------------------------
    async def generate_mod_draft(
        self,
        situation: str,
        context_chunks: list[dict],
        system_prompt: str,
    ) -> ProviderResponse:
        context_block = format_chunks(context_chunks)

        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Context (rules & mod notes):\n{context_block}\n\n"
                        f"Situation: {situation}"
                    ),
                }
            ],
            temperature=0.4,
        )

        return ProviderResponse(
            text=resp.content[0].text,
            provider_name="anthropic",
            model=self._model,
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        )

    # ------------------------------------------------------------------
    async def generate_moderation_analysis(
        self,
        message_content: str,
        rule_chunks: list[dict],
        system_prompt: str,
    ) -> ProviderResponse:
        context_block = format_chunks(rule_chunks)

        # Anthropic has no response_format — prompt instructs JSON output.
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Community rules:\n{context_block}\n\n"
                        f"Message to analyze:\n{message_content}"
                    ),
                }
            ],
            temperature=0.2,
        )

        return ProviderResponse(
            text=resp.content[0].text,
            provider_name="anthropic",
            model=self._model,
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        )
