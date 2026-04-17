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

        guild_id = str(message.guild.id) if message.guild is not None else None
        user_id = str(message.author.id)

        # 1. Run analysis — forward Discord context so the backend's
        #    progressive-discipline engine can update the per-user ledger.
        data = await client.analyze(
            message.content,
            source="discord",
            discord_user_id=user_id,
            discord_guild_id=guild_id,
        )

        # 2. Ignore clean messages
        if data.get("suggested_action") == "no_action":
            return

        # 3. Backend decided auto_actioned — delete + apply discipline.
        if data.get("status") == "auto_actioned":
            await self._delete_message(message)
            await self._apply_discipline(message, data)
            return

        # 4. Non-auto path: just alert mods for medium/high/critical severity.
        severity = data.get("severity", "")
        if severity in ("medium", "high", "critical"):
            embed = build_moderation_alert(data, message)
            embed.set_footer(text="Pending moderator review — check dashboard")
            await message.channel.send(embed=embed)

    # ── action pipeline ───────────────────────────────────────────────

    async def _delete_message(self, message: discord.Message) -> None:
        """Swallow expected failure modes so the pipeline continues."""
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

    async def _apply_discipline(
        self,
        message: discord.Message,
        data: dict,
    ) -> None:
        """Execute the backend's discipline decision and post an alert embed.

        Test mode: still emits the alert embed so mods can see what *would*
        have happened, but skips the actual member.kick/ban call.
        """
        decision = data.get("discipline_decision") or {}
        action = decision.get("action", "none")
        test_mode = bool(decision.get("test_mode"))

        executed: str | None = None
        if action == "warn":
            executed = "Warned"
        elif action == "kick":
            executed = await self._kick_member(message, reason=decision.get("reason"), test_mode=test_mode)
        elif action == "timed_ban":
            executed = await self._timed_ban_member(
                message,
                reason=decision.get("reason"),
                ban_minutes=decision.get("ban_minutes"),
                test_mode=test_mode,
            )
        # action == 'none' or missing: just fall through to the alert

        embed = build_moderation_alert(data, message)
        footer_parts = ["Message auto-deleted (demo mode)"]
        if executed:
            footer_parts.append(executed)
        if test_mode:
            footer_parts.append("TEST MODE — no real Discord action")
        embed.set_footer(text=" · ".join(footer_parts))
        await message.channel.send(embed=embed)

    async def _kick_member(
        self,
        message: discord.Message,
        *,
        reason: str | None,
        test_mode: bool,
    ) -> str:
        if test_mode:
            log.info(
                "TEST MODE kick would target user=%s in guild=%s reason=%r",
                message.author.id,
                getattr(message.guild, "id", None),
                reason,
            )
            return "Would have kicked"

        if message.guild is None:
            log.warning("Kick skipped — message has no guild context")
            return "Kick skipped (no guild)"

        # Members intent is not enabled, so the member cache is always cold;
        # fall back to the message author (any Snowflake works with Guild.kick).
        member = message.guild.get_member(message.author.id)
        target: discord.abc.Snowflake = member or message.author
        try:
            await message.guild.kick(
                target,
                reason=reason or "Progressive discipline: kick",
            )
            return "User kicked"
        except discord.Forbidden:
            log.warning("Missing permissions to kick %s", message.author.id)
            return "Kick skipped (missing permission)"
        except discord.HTTPException as exc:
            log.warning("Kick failed for %s: %s", message.author.id, exc)
            return "Kick failed"

    async def _timed_ban_member(
        self,
        message: discord.Message,
        *,
        reason: str | None,
        ban_minutes: int | None,
        test_mode: bool,
    ) -> str:
        """Issue a ban; auto-unban handling is left to a follow-up PR.

        For now the embed footer advertises the duration so a moderator can
        lift the ban manually via the portal's Undo button. A scheduled
        unban worker is out of scope for this commit — the ban is real,
        the lift is a moderator action.
        """
        label = f"{ban_minutes}-minute ban" if ban_minutes else "Timed ban"

        if test_mode:
            log.info(
                "TEST MODE %s would target user=%s in guild=%s reason=%r",
                label,
                message.author.id,
                getattr(message.guild, "id", None),
                reason,
            )
            return f"Would have issued {label}"

        member = message.guild.get_member(message.author.id) if message.guild else None
        target: discord.abc.Snowflake | None = member or message.author
        try:
            # Passing a User object still works — discord.py accepts anything with an `.id`.
            await message.guild.ban(
                target,
                reason=reason or f"Progressive discipline: {label}",
                delete_message_days=0,
            )
            return f"User banned ({label})"
        except discord.Forbidden:
            log.warning("Missing permissions to ban %s", message.author.id)
            return "Ban skipped (missing permission)"
        except discord.HTTPException as exc:
            log.warning("Ban failed for %s: %s", message.author.id, exc)
            return "Ban failed"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MonitorCog(bot))
