"""Tests for generate_chat_reply on both providers + provider_service dispatch.

All tests use mocked SDK clients — no network calls in CI.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.base import ProviderResponse
from providers.openai_provider import OpenAIProvider
from providers.anthropic_provider import AnthropicProvider


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SAMPLE_MESSAGES = [
    {"role": "user", "content": "hey modbot who won the spring major?"},
    {"role": "assistant", "content": "gg mention — checking that now"},
    {"role": "user", "content": "actually just tell me the bracket"},
]

SYSTEM_PROMPT = "You are ModBot, a casual gamer sidekick."
MAX_TOKENS = 300


# ---------------------------------------------------------------------------
# OpenAI — generate_chat_reply
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_generate_chat_reply_returns_normalized_response():
    """OpenAI provider returns a ProviderResponse with expected fields."""
    mock_choice = MagicMock()
    mock_choice.message.content = "lol nice — bracket's on the board"

    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.usage.prompt_tokens = 42
    mock_resp.usage.completion_tokens = 12

    mock_create = AsyncMock(return_value=mock_resp)

    with patch("providers.openai_provider.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create
        mock_cls.return_value = mock_client

        provider = OpenAIProvider()
        result = await provider.generate_chat_reply(
            messages=SAMPLE_MESSAGES,
            system_prompt=SYSTEM_PROMPT,
            max_tokens=MAX_TOKENS,
        )

    assert isinstance(result, ProviderResponse)
    assert result.text == "lol nice — bracket's on the board"
    assert result.provider_name == "openai"
    assert isinstance(result.model, str) and result.model
    assert result.usage["prompt_tokens"] == 42
    assert result.usage["completion_tokens"] == 12


@pytest.mark.asyncio
async def test_openai_generate_chat_reply_prepends_system_message():
    """OpenAI provider puts system_prompt as messages[0] with role='system'."""
    captured_kwargs = {}

    async def capture_create(**kwargs):
        captured_kwargs.update(kwargs)
        mock_choice = MagicMock()
        mock_choice.message.content = "gg"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage.prompt_tokens = 10
        mock_resp.usage.completion_tokens = 1
        return mock_resp

    with patch("providers.openai_provider.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create = capture_create
        mock_cls.return_value = mock_client

        provider = OpenAIProvider()
        await provider.generate_chat_reply(
            messages=SAMPLE_MESSAGES,
            system_prompt=SYSTEM_PROMPT,
            max_tokens=MAX_TOKENS,
        )

    sent_messages = captured_kwargs["messages"]
    assert sent_messages[0]["role"] == "system"
    assert sent_messages[0]["content"] == SYSTEM_PROMPT
    # The user/assistant turns follow after the system message
    assert sent_messages[1:] == SAMPLE_MESSAGES
    assert captured_kwargs["max_tokens"] == MAX_TOKENS


# ---------------------------------------------------------------------------
# Anthropic — generate_chat_reply
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anthropic_generate_chat_reply_returns_normalized_response():
    """Anthropic provider returns a ProviderResponse with expected fields."""
    mock_content = MagicMock()
    mock_content.text = "lol nah, not doing that. wanna ask about events instead?"

    mock_resp = MagicMock()
    mock_resp.content = [mock_content]
    mock_resp.usage.input_tokens = 55
    mock_resp.usage.output_tokens = 18

    mock_create = AsyncMock(return_value=mock_resp)

    with patch("providers.anthropic_provider.AsyncAnthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_cls.return_value = mock_client

        provider = AnthropicProvider()
        result = await provider.generate_chat_reply(
            messages=SAMPLE_MESSAGES,
            system_prompt=SYSTEM_PROMPT,
            max_tokens=MAX_TOKENS,
        )

    assert isinstance(result, ProviderResponse)
    assert "wanna ask about events" in result.text
    assert result.provider_name == "anthropic"
    assert isinstance(result.model, str) and result.model
    assert result.usage["input_tokens"] == 55
    assert result.usage["output_tokens"] == 18


@pytest.mark.asyncio
async def test_anthropic_generate_chat_reply_passes_system_as_top_level_kwarg():
    """Anthropic passes system= top-level, NOT inside messages list."""
    captured_kwargs = {}

    async def capture_create(**kwargs):
        captured_kwargs.update(kwargs)
        mock_content = MagicMock()
        mock_content.text = "gg"
        mock_resp = MagicMock()
        mock_resp.content = [mock_content]
        mock_resp.usage.input_tokens = 5
        mock_resp.usage.output_tokens = 1
        return mock_resp

    with patch("providers.anthropic_provider.AsyncAnthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create = capture_create
        mock_cls.return_value = mock_client

        provider = AnthropicProvider()
        await provider.generate_chat_reply(
            messages=SAMPLE_MESSAGES,
            system_prompt=SYSTEM_PROMPT,
            max_tokens=MAX_TOKENS,
        )

    # system= must be a top-level kwarg, not buried in messages
    assert captured_kwargs["system"] == SYSTEM_PROMPT
    assert captured_kwargs["messages"] == SAMPLE_MESSAGES
    assert captured_kwargs["max_tokens"] == MAX_TOKENS

    # Crucially: no message in the messages list should have role="system"
    for msg in captured_kwargs["messages"]:
        assert msg.get("role") != "system", (
            "system_prompt must not appear inside messages for Anthropic"
        )


# ---------------------------------------------------------------------------
# provider_service dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_provider_service_dispatches_generate_chat_reply():
    """provider_service.call('generate_chat_reply', ...) exercises the real dispatch.

    The mock target is _PROVIDERS[<primary>].generate_chat_reply — one layer
    BELOW provider_service.call — so the real dispatch logic runs: provider
    lookup via _get_provider, getattr resolution of method_name, and kwargs
    forwarding via await fn(**kwargs).  If any of those steps break, this
    test fails.

    Reads the primary provider from settings so the test stays correct when
    PRIMARY_PROVIDER changes (was openai, now anthropic).
    """
    import services.provider_service as _ps
    from config import settings

    primary = settings.PRIMARY_PROVIDER
    expected = ProviderResponse(
        text="locked in, checking that",
        provider_name=primary,
        model="mock-model",
        usage={"prompt_tokens": 20, "completion_tokens": 5},
    )
    mock_method = AsyncMock(return_value=expected)

    with patch.object(_ps._PROVIDERS[primary], "generate_chat_reply", mock_method):
        from services import provider_service

        result = await provider_service.call(
            "generate_chat_reply",
            messages=SAMPLE_MESSAGES,
            system_prompt=SYSTEM_PROMPT,
            max_tokens=MAX_TOKENS,
        )

    mock_method.assert_awaited_once_with(
        messages=SAMPLE_MESSAGES,
        system_prompt=SYSTEM_PROMPT,
        max_tokens=MAX_TOKENS,
    )
    assert result.text == "locked in, checking that"
    assert result.provider_name == primary


# ---------------------------------------------------------------------------
# Import sanity / regression guard (gotcha #3)
# ---------------------------------------------------------------------------

def test_provider_service_imports_after_abstract_method_added():
    """Regression guard: each concrete provider must OVERRIDE all abstract methods.

    Catches gotcha #3: someone adds @abstractmethod to BaseLLMProvider and
    forgets to implement it in a concrete provider class.  Python's ABC
    machinery raises TypeError when you instantiate a class that inherits but
    does not override an abstract method — exactly what building _PROVIDERS = {}
    does on module import.

    The prior implementation used inspect.getmembers() which returns INHERITED
    methods, so it could not catch the missing-override case: if OpenAIProvider
    inherited generate_chat_reply from BaseLLMProvider without defining its own
    body, getmembers() would still find it and the assertion would pass — even
    though _PROVIDERS construction would raise TypeError in production.

    This version calls each provider's constructor directly.  If generate_chat_reply
    (or any other abstract method) is not overridden, Python raises TypeError before
    __init__ returns, and pytest.fail() surfaces the exact set of missing methods.
    Mental simulation: delete the generate_chat_reply body from openai_provider.py
    so it inherits the abstract stub — OpenAIProvider() raises TypeError here, test
    fails loudly.  That is the correct behaviour.
    """
    from providers.openai_provider import OpenAIProvider
    from providers.anthropic_provider import AnthropicProvider

    for ProviderCls in (OpenAIProvider, AnthropicProvider):
        try:
            ProviderCls()
        except TypeError as exc:
            pytest.fail(
                f"{ProviderCls.__name__} is missing abstract method implementations: "
                f"{getattr(ProviderCls, '__abstractmethods__', 'unknown')}. "
                f"Original error: {exc}"
            )
