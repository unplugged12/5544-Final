"""Conversational @ModBot listener — sandbox channel only."""

from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands

from api_client import BackendClient
from chat_ratelimit import ChatRateLimiter

log = logging.getLogger(__name__)


class ChatCog(commands.Cog):
    """
    Conversational @ModBot listener. Coexistence with MonitorCog is by design:
    both fire on sandbox channel messages. Monitor handles moderation; this cog
    handles casual chat.

    When a human sends '@ModBot ...' in the sandbox:
    - MonitorCog runs moderation analysis (always).
    - ChatCog checks the mention/reply trigger and, if matched, calls the
      backend chat endpoint and replies.

    In demo mode, if MonitorCog auto-deletes the triggering message before
    this cog can reply, message.reply() raises discord.NotFound. This is
    caught and silently dropped in _safe_reply — it is not an error condition.
    Both responses (mod alert embed + casual reply) appearing together is
    acceptable for v1: they address different audiences (mods vs. the user).
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.ratelimit = ChatRateLimiter(
            user_per_min=bot.config.chat_max_user_per_min,
            guild_per_min=bot.config.chat_max_guild_per_min,
        )
        # (cached_value: bool | None, fetched_at_monotonic: float)
        self._kill_switch_cache: tuple[bool | None, float] = (None, 0.0)

    # ── listener ──────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Handle every message; gate to sandbox-channel mentions/replies."""
        try:
            await self._handle_message(message)
        except Exception:
            # All errors caught — the bot must never crash from chat.
            log.exception("ChatCog error for message %s", message.id)

    async def _handle_message(self, message: discord.Message) -> None:
        # Skip bots (including self)
        if message.author.bot:
            return

        # Skip DMs
        if message.guild is None:
            return

        # Gate: sandbox channel only (v1 — no allowlist field per plan)
        if message.channel.id != self.bot.config.sandbox_channel_id:
            return

        # Trigger gate: @mention OR reply-to-bot
        triggered_by_mention = self.bot.user in message.mentions
        triggered_by_reply = False

        # Only check the reply path (potentially expensive) when mention didn't
        # already trigger — avoids an HTTP call on every @-mention path.
        if not triggered_by_mention and message.reference is not None:
            resolved = message.reference.resolved
            if isinstance(resolved, discord.Message):
                triggered_by_reply = resolved.author.id == self.bot.user.id
            elif resolved is None and message.reference.message_id is not None:
                # Cache miss (e.g. bot restart, deep history) — fetch to determine
                # the referenced message's author.  Fail closed on any error so a
                # transient Discord fault can't accidentally trigger chat.
                try:
                    referenced = await message.channel.fetch_message(
                        message.reference.message_id
                    )
                    triggered_by_reply = referenced.author.id == self.bot.user.id
                except (discord.NotFound, discord.Forbidden):
                    pass  # message inaccessible — treat as no trigger
                except discord.HTTPException as exc:
                    log.warning(
                        "failed to fetch reply reference %s in channel %s: %s",
                        message.reference.message_id,
                        message.channel.id,
                        exc,
                    )
            # discord.DeletedReferencedMessage and any other resolved type:
            # leave triggered_by_reply=False

        if not (triggered_by_mention or triggered_by_reply):
            return

        # Kill switch 1: env var (CHAT_ENABLED) via config
        if not self.bot.config.chat_enabled:
            return

        # Kill switch 2: DB flag (cached 30 s, fails open)
        if not await self._chat_enabled_db():
            return

        # Rate limit (per-user and per-guild sliding windows)
        if not self.ratelimit.allow(
            user_id=str(message.author.id),
            guild_id=str(message.guild.id),
        ):
            # Silent drop — a "you are rate-limited" reply is itself spammable
            return

        # Strip bot mention from content before forwarding
        bot_id = (
            message.guild.me.id if message.guild.me is not None else self.bot.user.id
        )
        content = self._strip_bot_mention(message.content, bot_id)
        if not content.strip():
            # Bare mention with no content — nothing meaningful to forward
            return

        # Call backend chat endpoint
        client = BackendClient(self.bot.http_session)
        try:
            response = await client.chat(
                user_id=str(message.author.id),
                channel_id=str(message.channel.id),
                guild_id=str(message.guild.id),
                content=content,
            )
        except Exception as exc:
            log.exception("chat backend call failed: %s", exc)
            return  # fail silent — no error reply (also spammable)

        # PR 7: if the backend flagged an injection marker, record it in the
        # rate limiter for auto-timeout tracking (> 5 hits in 10 min → 1h ban).
        if response.get("injection_marker_seen", False):
            self.ratelimit.record_injection_marker(user_id=str(message.author.id))

        # Reply with constrained AllowedMentions (no mass-mention abuse)
        await self._safe_reply(
            message,
            response["reply_text"],
            allowed_mentions=discord.AllowedMentions(
                users=[message.author],
                everyone=False,
                roles=False,
                replied_user=True,
            ),
        )

    # ── helpers ───────────────────────────────────────────────────────

    async def _safe_reply(
        self,
        message: discord.Message,
        text: str,
        *,
        allowed_mentions: discord.AllowedMentions,
    ) -> None:
        """Reply, swallowing NotFound/Forbidden.

        NotFound: monitor cog may have auto-deleted the message in demo mode
        before this cog could reply — this is not an error.
        Forbidden: bot lacks channel send permissions.
        """
        try:
            await message.reply(text, allowed_mentions=allowed_mentions)
        except discord.NotFound:
            log.debug(
                "chat reply skipped — message %s already deleted (likely by monitor cog)",
                message.id,
            )
        except discord.Forbidden:
            log.warning(
                "chat reply forbidden — bot lacks permission in channel %s",
                message.channel.id,
            )

    async def _chat_enabled_db(self) -> bool:
        """Check DB kill switch; cache for 30 s. Fails open on backend errors."""
        cached_value, cached_at = self._kill_switch_cache
        now = time.monotonic()
        if cached_value is not None and now - cached_at < 30.0:
            return cached_value

        client = BackendClient(self.bot.http_session)
        try:
            value = await client.get_chat_enabled()
        except Exception:
            # Fail open — transient backend issues must not kill the chat feature
            log.debug("chat_enabled DB check failed; defaulting to enabled")
            value = True

        self._kill_switch_cache = (value, now)
        return value

    @staticmethod
    def _strip_bot_mention(content: str, bot_user_id: int) -> str:
        """Remove <@bot_id> and <@!bot_id> tokens from content."""
        for token in (f"<@{bot_user_id}>", f"<@!{bot_user_id}>"):
            content = content.replace(token, "", 1)
        return content.strip()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ChatCog(bot))
