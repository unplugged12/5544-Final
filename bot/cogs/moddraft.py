"""Slash command: /moddraft — draft a moderator response."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from api_client import BackendClient
from embeds import build_task_embed

log = logging.getLogger(__name__)


class ModDraftCog(commands.Cog):
    """Handles the /moddraft slash command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="moddraft", description="Draft a moderator response for a situation"
    )
    @app_commands.describe(situation="Describe the moderation situation")
    async def moddraft(self, interaction: discord.Interaction, situation: str) -> None:
        await interaction.response.defer()
        try:
            client = BackendClient(self.bot.http_session)
            data = await client.mod_draft(situation)
            embed = build_task_embed("Moderator Draft", data, discord.Color.green())
            await interaction.followup.send(embed=embed)
        except Exception:
            log.exception("Error in /moddraft")
            await interaction.followup.send(
                "An error occurred while processing your request. Please try again.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModDraftCog(bot))
