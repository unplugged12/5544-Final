"""Slash command: /summarize — summarize an announcement or long text."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from api_client import BackendClient
from embeds import build_task_embed

log = logging.getLogger(__name__)


class SummarizeCog(commands.Cog):
    """Handles the /summarize slash command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="summarize", description="Summarize an announcement or long text"
    )
    @app_commands.describe(text="The text to summarize")
    async def summarize(self, interaction: discord.Interaction, text: str) -> None:
        await interaction.response.defer()
        try:
            client = BackendClient(self.bot.http_session)
            data = await client.summarize(text)
            embed = build_task_embed("Announcement Summary", data, discord.Color.blue())
            await interaction.followup.send(embed=embed)
        except Exception:
            log.exception("Error in /summarize")
            await interaction.followup.send(
                "An error occurred while processing your request. Please try again.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SummarizeCog(bot))
