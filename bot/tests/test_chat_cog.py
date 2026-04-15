"""Tests for the ChatCog — all mocked, no Discord connection required."""

from __future__ import annotations

import sys
import os
import time
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# Ensure bot/ is on sys.path so imports inside cogs work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import discord

# We need to import ChatCog without a live bot.
# The cog module does "from api_client import BackendClient" and
# "from chat_ratelimit import ChatRateLimiter" — both are available on path.
from cogs.chat import ChatCog
from chat_ratelimit import ChatRateLimiter


# ── shared helpers ─────────────────────────────────────────────────────────────

SANDBOX_CHANNEL_ID = 111_111_111
OTHER_CHANNEL_ID = 222_222_222
BOT_USER_ID = 999_999_999
GUILD_ID = 333_333_333
AUTHOR_ID = 444_444_444


def _make_config(
    *,
    sandbox_channel_id: int = SANDBOX_CHANNEL_ID,
    chat_enabled: bool = True,
    chat_max_user_per_min: int = 6,
    chat_max_guild_per_min: int = 60,
) -> MagicMock:
    cfg = MagicMock()
    cfg.sandbox_channel_id = sandbox_channel_id
    cfg.chat_enabled = chat_enabled
    cfg.chat_max_user_per_min = chat_max_user_per_min
    cfg.chat_max_guild_per_min = chat_max_guild_per_min
    return cfg


def _make_bot_user(user_id: int = BOT_USER_ID) -> MagicMock:
    u = MagicMock(spec=discord.ClientUser)
    u.id = user_id
    return u


def _make_guild_me(user_id: int = BOT_USER_ID) -> MagicMock:
    me = MagicMock()
    me.id = user_id
    return me


def _make_guild(guild_id: int = GUILD_ID, me_id: int = BOT_USER_ID) -> MagicMock:
    g = MagicMock(spec=discord.Guild)
    g.id = guild_id
    g.me = _make_guild_me(me_id)
    return g


def _make_channel(channel_id: int = SANDBOX_CHANNEL_ID) -> MagicMock:
    ch = MagicMock(spec=discord.TextChannel)
    ch.id = channel_id
    return ch


def _make_author(
    author_id: int = AUTHOR_ID, *, is_bot: bool = False
) -> MagicMock:
    a = MagicMock(spec=discord.User)
    a.id = author_id
    a.bot = is_bot
    return a


def _make_message(
    *,
    content: str = "hello",
    channel_id: int = SANDBOX_CHANNEL_ID,
    author_id: int = AUTHOR_ID,
    author_is_bot: bool = False,
    guild: MagicMock | None = None,
    mentions: list | None = None,
    reference: MagicMock | None = None,
) -> MagicMock:
    msg = MagicMock(spec=discord.Message)
    msg.id = 123456789
    msg.content = content
    msg.author = _make_author(author_id, is_bot=author_is_bot)
    msg.channel = _make_channel(channel_id)
    msg.guild = guild if guild is not None else _make_guild()
    msg.mentions = mentions if mentions is not None else []
    msg.reference = reference
    msg.reply = AsyncMock()
    return msg


def _make_bot(
    *,
    config: MagicMock | None = None,
    user_id: int = BOT_USER_ID,
    chat_enabled_db: bool = True,
    chat_api_response: dict | None = None,
    api_raises: Exception | None = None,
    get_chat_enabled_raises: Exception | None = None,
) -> tuple[MagicMock, ChatCog]:
    """Build a mocked bot + ChatCog. Returns (bot, cog)."""
    cfg = config or _make_config()

    bot = MagicMock()
    bot.config = cfg
    bot.user = _make_bot_user(user_id)
    bot.http_session = MagicMock()

    cog = ChatCog(bot)

    # Patch the BackendClient that the cog instantiates inside _handle_message
    api_response = chat_api_response or {"reply_text": "gg, what's up?"}

    mock_client = MagicMock()
    if api_raises:
        mock_client.chat = AsyncMock(side_effect=api_raises)
    else:
        mock_client.chat = AsyncMock(return_value=api_response)

    if get_chat_enabled_raises:
        mock_client.get_chat_enabled = AsyncMock(
            side_effect=get_chat_enabled_raises
        )
    else:
        mock_client.get_chat_enabled = AsyncMock(return_value=chat_enabled_db)

    bot._mock_client = mock_client
    return bot, cog, mock_client


async def _run_on_message(
    cog: ChatCog,
    message: MagicMock,
    *,
    mock_client: MagicMock | None = None,
    patch_backend: bool = True,
) -> None:
    """Invoke cog.on_message, optionally with a patched BackendClient."""
    if patch_backend and mock_client is not None:
        with patch("cogs.chat.BackendClient", return_value=mock_client):
            await cog.on_message(message)
    else:
        await cog.on_message(message)


# ── basic gate tests ──────────────────────────────────────────────────────────

class TestGates:
    @pytest.mark.asyncio
    async def test_bot_author_skipped(self) -> None:
        bot, cog, mock_client = _make_bot()
        msg = _make_message(author_is_bot=True)
        await _run_on_message(cog, msg, mock_client=mock_client)
        mock_client.chat.assert_not_called()
        msg.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_dm_skipped(self) -> None:
        bot, cog, mock_client = _make_bot()
        msg = _make_message(guild=None)
        msg.guild = None  # explicit DM
        await _run_on_message(cog, msg, mock_client=mock_client)
        mock_client.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_sandbox_channel_no_api_call(self) -> None:
        bot, cog, mock_client = _make_bot()
        msg = _make_message(channel_id=OTHER_CHANNEL_ID)
        await _run_on_message(cog, msg, mock_client=mock_client)
        mock_client.chat.assert_not_called()
        msg.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_trigger_bare_message(self) -> None:
        """Sandbox message with no mention and no reply-to-bot — no API call."""
        bot, cog, mock_client = _make_bot()
        msg = _make_message(mentions=[], reference=None)
        await _run_on_message(cog, msg, mock_client=mock_client)
        mock_client.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_bare_mention_no_content_skipped(self) -> None:
        """@mention with no text content beyond the mention token — skipped."""
        bot, cog, mock_client = _make_bot()
        bot_user = bot.user
        msg = _make_message(
            content=f"<@{BOT_USER_ID}>",
            mentions=[bot_user],
        )
        await _run_on_message(cog, msg, mock_client=mock_client)
        mock_client.chat.assert_not_called()


# ── trigger tests ─────────────────────────────────────────────────────────────

class TestTriggers:
    @pytest.mark.asyncio
    async def test_mention_triggers_api(self) -> None:
        bot, cog, mock_client = _make_bot()
        bot_user = bot.user
        msg = _make_message(
            content=f"<@{BOT_USER_ID}> hey there",
            mentions=[bot_user],
        )
        await _run_on_message(cog, msg, mock_client=mock_client)
        mock_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_reply_to_bot_triggers_api(self) -> None:
        bot, cog, mock_client = _make_bot()

        # Build a resolved reference pointing at a bot message
        bot_msg = MagicMock(spec=discord.Message)
        bot_msg.author = MagicMock()
        bot_msg.author.id = BOT_USER_ID

        ref = MagicMock(spec=discord.MessageReference)
        ref.resolved = bot_msg

        msg = _make_message(
            content="cool reply",
            mentions=[],  # not a mention
            reference=ref,
        )
        await _run_on_message(cog, msg, mock_client=mock_client)
        mock_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_mention_stripped_from_content(self) -> None:
        """The bot mention token is stripped; backend receives clean content."""
        bot, cog, mock_client = _make_bot()
        bot_user = bot.user
        msg = _make_message(
            content=f"<@{BOT_USER_ID}> hi",
            mentions=[bot_user],
        )
        await _run_on_message(cog, msg, mock_client=mock_client)
        call_kwargs = mock_client.chat.call_args.kwargs
        assert call_kwargs["content"] == "hi"

    @pytest.mark.asyncio
    async def test_mention_not_stripped_from_non_bot(self) -> None:
        """Non-bot mention is not removed from content forwarded to backend."""
        bot, cog, mock_client = _make_bot()
        bot_user = bot.user
        OTHER_USER_ID = 777
        msg = _make_message(
            content=f"<@{BOT_USER_ID}> ping <@{OTHER_USER_ID}>",
            mentions=[bot_user],
        )
        await _run_on_message(cog, msg, mock_client=mock_client)
        call_kwargs = mock_client.chat.call_args.kwargs
        # Bot mention stripped; other mention preserved
        assert f"<@{OTHER_USER_ID}>" in call_kwargs["content"]
        assert f"<@{BOT_USER_ID}>" not in call_kwargs["content"]


# ── kill switch tests ─────────────────────────────────────────────────────────

class TestKillSwitches:
    @pytest.mark.asyncio
    async def test_env_kill_switch_disabled(self) -> None:
        """config.chat_enabled=False stops before API call."""
        cfg = _make_config(chat_enabled=False)
        bot, cog, mock_client = _make_bot(config=cfg)
        bot_user = bot.user
        msg = _make_message(
            content=f"<@{BOT_USER_ID}> hey",
            mentions=[bot_user],
        )
        await _run_on_message(cog, msg, mock_client=mock_client)
        mock_client.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_kill_switch_disabled(self) -> None:
        """get_chat_enabled() returns False — API call suppressed."""
        bot, cog, mock_client = _make_bot(chat_enabled_db=False)
        bot_user = bot.user
        msg = _make_message(
            content=f"<@{BOT_USER_ID}> hey",
            mentions=[bot_user],
        )
        await _run_on_message(cog, msg, mock_client=mock_client)
        mock_client.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_kill_switch_cached_30s(self) -> None:
        """Second call within 30 s must not re-query the backend."""
        bot, cog, mock_client = _make_bot(chat_enabled_db=True)
        bot_user = bot.user

        def _make_msg() -> MagicMock:
            return _make_message(
                content=f"<@{BOT_USER_ID}> hello",
                mentions=[bot_user],
            )

        with patch("cogs.chat.BackendClient", return_value=mock_client):
            await cog.on_message(_make_msg())
            await cog.on_message(_make_msg())

        # get_chat_enabled should only be called once (second within 30 s cache)
        assert mock_client.get_chat_enabled.call_count == 1

    @pytest.mark.asyncio
    async def test_db_kill_switch_cache_expires(self) -> None:
        """After 30 s the DB is re-queried."""
        bot, cog, mock_client = _make_bot(chat_enabled_db=True)
        bot_user = bot.user

        def _make_msg() -> MagicMock:
            return _make_message(
                content=f"<@{BOT_USER_ID}> hello",
                mentions=[bot_user],
            )

        base = 1000.0
        with patch("cogs.chat.time") as mock_time:
            mock_time.monotonic.return_value = base
            with patch("cogs.chat.BackendClient", return_value=mock_client):
                await cog._handle_message(_make_msg())
                # Advance past 30 s
                mock_time.monotonic.return_value = base + 31.0
                await cog._handle_message(_make_msg())

        assert mock_client.get_chat_enabled.call_count == 2

    @pytest.mark.asyncio
    async def test_db_kill_switch_fail_open(self) -> None:
        """If get_chat_enabled raises, the cog defaults to enabled (fail open)."""
        bot, cog, mock_client = _make_bot(
            get_chat_enabled_raises=RuntimeError("backend down")
        )
        bot_user = bot.user
        msg = _make_message(
            content=f"<@{BOT_USER_ID}> hey",
            mentions=[bot_user],
        )
        await _run_on_message(cog, msg, mock_client=mock_client)
        # Despite get_chat_enabled raising, chat API should be called (fail open)
        mock_client.chat.assert_called_once()


# ── rate limit tests ──────────────────────────────────────────────────────────

class TestRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limited_drop_no_reply(self) -> None:
        """When rate limited, no API call and no reply are made."""
        cfg = _make_config(chat_max_user_per_min=1)
        bot, cog, mock_client = _make_bot(config=cfg)
        bot_user = bot.user

        def _make_msg() -> MagicMock:
            return _make_message(
                content=f"<@{BOT_USER_ID}> hello",
                mentions=[bot_user],
            )

        with patch("cogs.chat.BackendClient", return_value=mock_client):
            await cog.on_message(_make_msg())   # allowed
            second_msg = _make_msg()
            await cog.on_message(second_msg)    # rate-limited

        assert mock_client.chat.call_count == 1
        second_msg.reply.assert_not_called()


# ── error handling tests ──────────────────────────────────────────────────────

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_backend_error_swallowed_silently(self) -> None:
        """API client raises — no reply, no exception bubbles up."""
        bot, cog, mock_client = _make_bot(
            api_raises=RuntimeError("backend exploded")
        )
        bot_user = bot.user
        msg = _make_message(
            content=f"<@{BOT_USER_ID}> hey",
            mentions=[bot_user],
        )
        # Should not raise
        await _run_on_message(cog, msg, mock_client=mock_client)
        msg.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_found_swallowed(self) -> None:
        """discord.NotFound on reply is swallowed (monitor may have deleted the message)."""
        bot, cog, mock_client = _make_bot()
        bot_user = bot.user
        msg = _make_message(
            content=f"<@{BOT_USER_ID}> hey",
            mentions=[bot_user],
        )
        msg.reply = AsyncMock(
            side_effect=discord.NotFound(MagicMock(), "Unknown Message")
        )
        # Should not raise
        await _run_on_message(cog, msg, mock_client=mock_client)
        # reply was attempted, NotFound silently swallowed
        msg.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_forbidden_swallowed(self) -> None:
        """discord.Forbidden on reply is swallowed (bot lacks channel perms)."""
        bot, cog, mock_client = _make_bot()
        bot_user = bot.user
        msg = _make_message(
            content=f"<@{BOT_USER_ID}> hey",
            mentions=[bot_user],
        )
        msg.reply = AsyncMock(
            side_effect=discord.Forbidden(MagicMock(), "Missing Permissions")
        )
        # Should not raise
        await _run_on_message(cog, msg, mock_client=mock_client)
        msg.reply.assert_called_once()


# ── AllowedMentions test ──────────────────────────────────────────────────────

class TestAllowedMentions:
    @pytest.mark.asyncio
    async def test_allowed_mentions_on_reply(self) -> None:
        """Reply must be called with the correct AllowedMentions kwargs."""
        bot, cog, mock_client = _make_bot()
        bot_user = bot.user
        author = _make_author()
        msg = _make_message(
            content=f"<@{BOT_USER_ID}> hi",
            mentions=[bot_user],
        )
        msg.author = author  # ensure we can check the exact user ref

        await _run_on_message(cog, msg, mock_client=mock_client)

        msg.reply.assert_called_once()
        _, kwargs = msg.reply.call_args
        am = kwargs.get("allowed_mentions")
        assert am is not None, "allowed_mentions not passed to reply()"
        assert am.everyone is False
        assert am.roles is False
        assert am.replied_user is True
        assert author in am.users
