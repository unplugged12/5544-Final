"""OpenAI provider implementation using AsyncOpenAI."""

import logging

from openai import AsyncOpenAI

from config import settings
from providers.base import BaseLLMProvider, ProviderResponse
from providers.utils import format_chunks

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = settings.OPENAI_MODEL

    def _to_response(self, resp) -> ProviderResponse:
        return ProviderResponse(
            text=resp.choices[0].message.content or "",
            provider_name="openai",
            model=self._model,
            usage={
                "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
            },
        )

    # ------------------------------------------------------------------
    async def generate_grounded_answer(
        self,
        query: str,
        context_chunks: list[dict],
        system_prompt: str,
    ) -> ProviderResponse:
        context_block = format_chunks(context_chunks)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Context:\n{context_block}\n\nQuestion: {query}"
                ),
            },
        ]

        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.3,
        )

        return self._to_response(resp)

    # ------------------------------------------------------------------
    async def generate_summary(
        self,
        text: str,
        system_prompt: str,
    ) -> ProviderResponse:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Summarize this:\n\n{text}"},
        ]

        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.3,
        )

        return self._to_response(resp)

    # ------------------------------------------------------------------
    async def generate_mod_draft(
        self,
        situation: str,
        context_chunks: list[dict],
        system_prompt: str,
    ) -> ProviderResponse:
        context_block = format_chunks(context_chunks)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Context (rules & mod notes):\n{context_block}\n\n"
                    f"Situation: {situation}"
                ),
            },
        ]

        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.4,
        )

        return self._to_response(resp)

    # ------------------------------------------------------------------
    async def generate_moderation_analysis(
        self,
        message_content: str,
        rule_chunks: list[dict],
        system_prompt: str,
    ) -> ProviderResponse:
        context_block = format_chunks(rule_chunks)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Community rules:\n{context_block}\n\n"
                    f"Message to analyze:\n{message_content}"
                ),
            },
        ]

        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        return self._to_response(resp)

    # ------------------------------------------------------------------
    async def generate_chat_reply(
        self,
        messages: list[dict],  # [{role: "user"|"assistant", content: str}]
        system_prompt: str,
        max_tokens: int,
    ) -> ProviderResponse:
        full_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=full_messages,
            max_tokens=max_tokens,
            temperature=0.5,
        )

        return self._to_response(resp)
