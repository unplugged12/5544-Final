"""Slash command: /askfaq — query the community FAQ knowledge base."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from api_client import BackendClient
from embeds import build_task_embed

log = logging.getLogger(__name__)


class FaqCog(commands.Cog):
    """Handles the /askfaq slash command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="askfaq", description="Ask a community FAQ question")
    @app_commands.describe(question="The question to look up in the FAQ knowledge base")
    async def askfaq(self, interaction: discord.Interaction, question: str) -> None:
        await interaction.response.defer()
        try:
            client = BackendClient(self.bot.http_session)
            data = await client.ask_faq(question)
            embed = build_task_embed("FAQ Answer", data, discord.Color.blurple())
            await interaction.followup.send(embed=embed)
        except Exception:
            log.exception("Error in /askfaq")
            await interaction.followup.send(
                "An error occurred while processing your request. Please try again.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FaqCog(bot))
