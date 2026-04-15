"""Admin slash commands — privileged bot management operations.

PR 7: /toggle-chat enables/disables the conversational chat feature by
writing to the DB flag via the backend API. The change takes effect
immediately because the ChatCog's kill-switch cache is invalidated after
a successful toggle.

Security notes:
  - default_permissions(administrator=True) prevents the command from
    appearing in the slash-command list for non-admins (Discord enforced).
  - The explicit guild_permissions.administrator check in the handler is
    defense-in-depth: it rejects the interaction even if Discord's
    permission check is somehow bypassed (e.g., in DMs, or bot misconfiguration).
  - ephemeral=True on all responses so admin actions are not visible to
    the rest of the channel.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from api_client import BackendClient

log = logging.getLogger(__name__)


class AdminCog(commands.Cog):
    """Administrative slash commands for ModBot management."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="toggle-chat",
        description="Enable or disable conversational chat (admin only)",
    )
    @app_commands.default_permissions(administrator=True)
    async def toggle_chat(
        self,
        interaction: discord.Interaction,
        enabled: bool,
    ) -> None:
        """Enable or disable the @ModBot conversational chat feature.

        Writes the DB flag via the backend settings API. The ChatCog's
        kill-switch cache is invalidated immediately so the change takes
        effect on the next message (not after the 30s TTL expires).

        Args:
            enabled: True to enable chat, False to disable.
        """
        # Defense-in-depth: verify guild admin permission in code.
        # default_permissions handles the Discord-side gate; this check
        # covers edge cases (DMs, bot misconfiguration, future permission changes).
        if interaction.guild is None or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "admin only", ephemeral=True
            )
            return

        # Defer so we can make an async API call without hitting the 3s
        # interaction response deadline.
        await interaction.response.defer(ephemeral=True)

        client = BackendClient(self.bot.http_session)
        try:
            await client.set_chat_enabled(enabled)
        except Exception as exc:
            log.exception("toggle-chat: backend call failed: %s", exc)
            await interaction.followup.send(
                f"failed to update chat setting: {exc}", ephemeral=True
            )
            return

        # Invalidate the ChatCog's kill-switch cache so the change takes
        # effect immediately rather than waiting for the 30s TTL.
        chat_cog = self.bot.get_cog("ChatCog")
        if chat_cog is not None:
            chat_cog._kill_switch_cache = (None, 0.0)
            log.debug("toggle-chat: invalidated ChatCog kill-switch cache")

        status = "enabled" if enabled else "disabled"
        await interaction.followup.send(
            f"chat is now {status}", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
