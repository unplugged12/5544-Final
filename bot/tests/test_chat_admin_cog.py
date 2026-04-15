"""Tests for PR 7 — AdminCog /toggle-chat slash command.

Coverage:
  - Non-admin user → ephemeral "admin only", no API call
  - Admin user, chat enabled → API called with enabled=True, ephemeral confirmation
  - Admin user, chat disabled → API called with enabled=False, ephemeral confirmation
  - API call failure → ephemeral error message, no crash
  - Cache invalidation: after toggle, ChatCog._kill_switch_cache is reset to (None, 0.0)
"""

from __future__ import annotations

import sys
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# Ensure bot/ is on sys.path so imports inside cogs work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import discord
from cogs.admin import AdminCog
from cogs.chat import ChatCog
from chat_ratelimit import ChatRateLimiter


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_permissions(*, administrator: bool = True) -> MagicMock:
    perms = MagicMock(spec=discord.Permissions)
    perms.administrator = administrator
    return perms


def _make_guild(guild_id: int = 999_000) -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    guild.id = guild_id
    return guild


def _make_user(*, is_admin: bool = True, user_id: int = 42) -> MagicMock:
    user = MagicMock(spec=discord.Member)
    user.id = user_id
    user.guild_permissions = _make_permissions(administrator=is_admin)
    return user


def _make_interaction(*, is_admin: bool = True, user_id: int = 42) -> MagicMock:
    """Return a mock discord.Interaction with response/followup stubbed."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = _make_user(is_admin=is_admin, user_id=user_id)
    interaction.guild = _make_guild()

    # response.send_message and response.defer are async
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()

    # followup.send is async
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    return interaction


def _make_bot(*, has_chat_cog: bool = True) -> MagicMock:
    """Return a mock bot with an http_session and optional ChatCog."""
    bot = MagicMock()
    bot.http_session = MagicMock()

    if has_chat_cog:
        # We only need _kill_switch_cache on the cog — use a simple MagicMock
        chat_cog = MagicMock()
        chat_cog._kill_switch_cache = (True, 999.0)  # non-null cache
        bot.get_cog = MagicMock(return_value=chat_cog)
    else:
        bot.get_cog = MagicMock(return_value=None)

    return bot


# ── tests ──────────────────────────────────────────────────────────────────────

class TestToggleChatNonAdmin:
    @pytest.mark.asyncio
    async def test_non_admin_gets_rejected_without_api_call(self) -> None:
        """Non-admin user → ephemeral 'admin only', API never called."""
        bot = _make_bot()
        cog = AdminCog(bot)
        interaction = _make_interaction(is_admin=False)

        with patch("cogs.admin.BackendClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            await cog.toggle_chat.callback(cog, interaction, enabled=True)

        interaction.response.send_message.assert_called_once_with(
            "admin only", ephemeral=True
        )
        mock_client.set_chat_enabled.assert_not_called()

    @pytest.mark.asyncio
    async def test_dm_context_rejected(self) -> None:
        """Interaction in DM (guild=None) → rejected as non-admin."""
        bot = _make_bot()
        cog = AdminCog(bot)
        interaction = _make_interaction(is_admin=True)
        interaction.guild = None  # simulate DM

        with patch("cogs.admin.BackendClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            await cog.toggle_chat.callback(cog, interaction, enabled=True)

        interaction.response.send_message.assert_called_once_with(
            "admin only", ephemeral=True
        )
        mock_client.set_chat_enabled.assert_not_called()


class TestToggleChatAdmin:
    @pytest.mark.asyncio
    async def test_enable_chat_calls_api_and_confirms(self) -> None:
        """Admin enables chat → API called with enabled=True, confirmation sent."""
        bot = _make_bot()
        cog = AdminCog(bot)
        interaction = _make_interaction(is_admin=True)

        with patch("cogs.admin.BackendClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.set_chat_enabled = AsyncMock(return_value={"chat_enabled": True})
            mock_client_class.return_value = mock_client

            await cog.toggle_chat.callback(cog, interaction, enabled=True)

        mock_client.set_chat_enabled.assert_called_once_with(True)
        interaction.followup.send.assert_called_once()
        args = interaction.followup.send.call_args
        assert "enabled" in args[0][0] or "enabled" in str(args)

    @pytest.mark.asyncio
    async def test_disable_chat_calls_api_and_confirms(self) -> None:
        """Admin disables chat → API called with enabled=False, confirmation sent."""
        bot = _make_bot()
        cog = AdminCog(bot)
        interaction = _make_interaction(is_admin=True)

        with patch("cogs.admin.BackendClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.set_chat_enabled = AsyncMock(return_value={"chat_enabled": False})
            mock_client_class.return_value = mock_client

            await cog.toggle_chat.callback(cog, interaction, enabled=False)

        mock_client.set_chat_enabled.assert_called_once_with(False)
        interaction.followup.send.assert_called_once()
        args = interaction.followup.send.call_args
        assert "disabled" in args[0][0] or "disabled" in str(args)

    @pytest.mark.asyncio
    async def test_api_failure_sends_error_message_no_crash(self) -> None:
        """API call failure → ephemeral error message, no exception propagated."""
        bot = _make_bot()
        cog = AdminCog(bot)
        interaction = _make_interaction(is_admin=True)

        with patch("cogs.admin.BackendClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.set_chat_enabled = AsyncMock(side_effect=Exception("backend down"))
            mock_client_class.return_value = mock_client

            # Must not raise
            await cog.toggle_chat.callback(cog, interaction, enabled=True)

        # Should have sent an error message via followup
        interaction.followup.send.assert_called_once()
        msg = interaction.followup.send.call_args[0][0]
        assert "failed" in msg.lower() or "error" in msg.lower() or "backend" in msg.lower()

    @pytest.mark.asyncio
    async def test_cache_invalidated_after_successful_toggle(self) -> None:
        """After a successful toggle, ChatCog._kill_switch_cache is reset."""
        bot = _make_bot(has_chat_cog=True)
        chat_cog_mock = bot.get_cog.return_value
        # Set a non-null cache to verify it gets cleared
        chat_cog_mock._kill_switch_cache = (True, 999.0)

        cog = AdminCog(bot)
        interaction = _make_interaction(is_admin=True)

        with patch("cogs.admin.BackendClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.set_chat_enabled = AsyncMock(return_value={"chat_enabled": False})
            mock_client_class.return_value = mock_client

            await cog.toggle_chat.callback(cog, interaction, enabled=False)

        # Cache must be invalidated
        assert chat_cog_mock._kill_switch_cache == (None, 0.0), (
            f"Expected (None, 0.0), got {chat_cog_mock._kill_switch_cache}"
        )

    @pytest.mark.asyncio
    async def test_cache_invalidation_skipped_when_no_chat_cog(self) -> None:
        """If ChatCog is not loaded, cache invalidation is skipped without error."""
        bot = _make_bot(has_chat_cog=False)
        cog = AdminCog(bot)
        interaction = _make_interaction(is_admin=True)

        with patch("cogs.admin.BackendClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.set_chat_enabled = AsyncMock(return_value={"chat_enabled": True})
            mock_client_class.return_value = mock_client

            # Must not raise even if ChatCog is not registered
            await cog.toggle_chat.callback(cog, interaction, enabled=True)

        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_deferred_before_api_call(self) -> None:
        """interaction.response.defer() is called before the API call."""
        bot = _make_bot()
        cog = AdminCog(bot)
        interaction = _make_interaction(is_admin=True)

        call_order = []

        async def track_defer(*args, **kwargs):
            call_order.append("defer")

        async def track_api(*args, **kwargs):
            call_order.append("api")
            return {"chat_enabled": True}

        interaction.response.defer = AsyncMock(side_effect=track_defer)

        with patch("cogs.admin.BackendClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.set_chat_enabled = AsyncMock(side_effect=track_api)
            mock_client_class.return_value = mock_client

            await cog.toggle_chat.callback(cog, interaction, enabled=True)

        assert call_order.index("defer") < call_order.index("api"), (
            "defer() must be called before the API call"
        )
