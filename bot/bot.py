"""ModBot — discord.py 2.x Bot subclass with aiohttp session management."""

from __future__ import annotations

import logging

import aiohttp
import discord
from discord.ext import commands

from config import Config

log = logging.getLogger(__name__)

COG_EXTENSIONS: list[str] = [
    "cogs.faq",
    "cogs.summarize",
    "cogs.moddraft",
    "cogs.settings",
    "cogs.monitor",
    "cogs.chat",
]


class ModBot(commands.Bot):
    """Esports Mod Copilot Discord bot."""

    http_session: aiohttp.ClientSession

    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix="!", intents=intents)
        self.config = config

    async def setup_hook(self) -> None:
        """Called once before the bot connects to the gateway."""
        # Create a single shared aiohttp session for all backend calls
        self.http_session = aiohttp.ClientSession(
            base_url=self.config.backend_url,
            timeout=aiohttp.ClientTimeout(total=30),
        )

        # Load every cog
        for ext in COG_EXTENSIONS:
            try:
                await self.load_extension(ext)
                log.info("Loaded extension: %s", ext)
            except Exception:
                log.exception("Failed to load extension: %s", ext)

        # Sync the command tree to the configured guild for instant registration
        guild = discord.Object(id=self.config.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        log.info("Command tree synced to guild %s", self.config.guild_id)

    async def close(self) -> None:
        """Gracefully shut down the aiohttp session, then the bot."""
        await self.http_session.close()
        await super().close()
