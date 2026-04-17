"""Passive message monitor — analyses messages in the sandbox channel."""

from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands

from api_client import BackendClient
from embeds import build_moderation_alert

log = logging.getLogger(__name__)

# Per-user cooldown in seconds
COOLDOWN_SECONDS = 5.0


class MonitorCog(commands.Cog):
    """Listens for messages in the sandbox channel and runs moderation analysis."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # user_id -> monotonic timestamp of last analysis
        self._cooldowns: dict[int, float] = {}

    # ── helpers ────────────────────────────────────────────────────────

    def _on_cooldown(self, user_id: int) -> bool:
        """Return True if the user is still within the cooldown window."""
        now = time.monotonic()
        last = self._cooldowns.get(user_id, 0.0)
        if now - last < COOLDOWN_SECONDS:
            return True
        self._cooldowns[user_id] = now
        return False

    # ── listener ──────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Analyse every non-bot message in the sandbox channel."""
        try:
            await self._handle_message(message)
        except Exception:
            # All errors MUST be caught — the bot must never crash from monitoring.
            log.exception("Monitor error for message %s", message.id)

    async def _handle_message(self, message: discord.Message) -> None:
        # Filter 1: only the sandbox channel
        if message.channel.id != self.bot.config.sandbox_channel_id:
            return

        # Filter 2: ignore bots (including self)
        if message.author.bot:
            return

        # Filter 3: ignore empty / image-only messages
        if not message.content or not message.content.strip():
            return

        # Filter 4: per-user cooldown
        if self._on_cooldown(message.author.id):
            return

        client = BackendClient(self.bot.http_session)

        # 1. Run analysis
        data = await client.analyze(message.content, source="discord")

        # 2. Ignore clean messages
        if data.get("suggested_action") == "no_action":
            return

        # 3. Backend already decided demo-mode action — trust the status field.
        #    (moderation_service.analyze sets status=auto_actioned when demo_mode
        #    is on AND the action is one of the auto-delete triggers.)
        if data.get("status") == "auto_actioned":
            try:
                await message.delete()
            except discord.Forbidden:
                log.warning(
                    "Missing permissions to delete message %s in #%s",
                    message.id,
                    message.channel,
                )
            except discord.NotFound:
                log.debug("Message %s already deleted", message.id)

            embed = build_moderation_alert(data, message)
            embed.set_footer(text="Message auto-deleted (demo mode)")
            await message.channel.send(embed=embed)

        else:
            # Non-demo: alert for medium/high/critical severity
            severity = data.get("severity", "")
            if severity in ("medium", "high", "critical"):
                embed = build_moderation_alert(data, message)
                embed.set_footer(text="Pending moderator review — check dashboard")
                await message.channel.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MonitorCog(bot))
