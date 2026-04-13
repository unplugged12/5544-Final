"""Provider service — primary/fallback LLM dispatch."""

import logging

import anthropic
import openai

from config import settings
from providers.anthropic_provider import AnthropicProvider
from providers.base import BaseLLMProvider, ProviderResponse
from providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, BaseLLMProvider] = {
    "openai": OpenAIProvider(),
    "anthropic": AnthropicProvider(),
}


def _get_provider(name: str) -> BaseLLMProvider:
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValueError(f"Unknown provider: {name}")
    return provider


async def call(method_name: str, **kwargs) -> ProviderResponse:
    """Call *method_name* on the primary provider, falling back on error.

    ``method_name`` must be one of the four abstract methods defined on
    ``BaseLLMProvider``.
    """
    primary_name = settings.PRIMARY_PROVIDER
    fallback_name = settings.FALLBACK_PROVIDER

    primary = _get_provider(primary_name)
    fn = getattr(primary, method_name, None)
    if fn is None:
        raise ValueError(f"Provider method not found: {method_name}")

    try:
        logger.info("Calling %s on primary provider (%s)", method_name, primary_name)
        return await fn(**kwargs)
    except (openai.APIError, anthropic.APIError) as exc:
        logger.warning(
            "Primary provider (%s) failed for %s: %s — falling back to %s",
            primary_name,
            method_name,
            exc,
            fallback_name,
        )

    # Fallback
    fallback = _get_provider(fallback_name)
    fallback_fn = getattr(fallback, method_name)
    logger.info("Calling %s on fallback provider (%s)", method_name, fallback_name)
    return await fallback_fn(**kwargs)
