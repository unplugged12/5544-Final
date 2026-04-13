"""Slash command: /toggle-demomode — toggle backend demo mode (admin only)."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from api_client import BackendClient

log = logging.getLogger(__name__)


class SettingsCog(commands.Cog):
    """Handles the /toggle-demomode slash command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="toggle-demomode", description="Toggle demo mode on or off (admin only)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def toggle_demomode(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        client = BackendClient(self.bot.http_session)

        current = await client.get_demo_mode()
        result = await client.set_demo_mode(not current)
        new_state = result.get("demo_mode", not current)

        state_label = "ON" if new_state else "OFF"
        color = discord.Color.green() if new_state else discord.Color.light_grey()

        embed = discord.Embed(
            title="Demo Mode Updated",
            description=f"Demo mode is now **{state_label}**.",
            color=color,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @toggle_demomode.error
    async def toggle_demomode_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need the **Manage Messages** permission to use this command.",
                ephemeral=True,
            )
        else:
            log.exception("Unexpected error in /toggle-demomode: %s", error)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An unexpected error occurred.", ephemeral=True
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SettingsCog(bot))
