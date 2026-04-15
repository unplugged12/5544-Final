"""Bot configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    """Immutable bot configuration."""

    discord_token: str
    guild_id: int
    sandbox_channel_id: int
    backend_url: str
    # Chat feature — env-var kill switch and rate-limit knobs.
    # v1 gates on sandbox_channel_id directly; no allowlist field (PR plan explicit).
    chat_enabled: bool
    chat_max_user_per_min: int
    chat_max_guild_per_min: int

    @classmethod
    def from_env(cls) -> Config:
        """Load configuration from environment / .env file."""
        load_dotenv()

        token = os.environ.get("DISCORD_TOKEN", "")
        if not token:
            raise ValueError("DISCORD_TOKEN environment variable is required")

        guild_id_raw = os.environ.get("DISCORD_GUILD_ID", "")
        if not guild_id_raw:
            raise ValueError("DISCORD_GUILD_ID environment variable is required")

        sandbox_id_raw = os.environ.get("SANDBOX_CHANNEL_ID", "")
        if not sandbox_id_raw:
            raise ValueError("SANDBOX_CHANNEL_ID environment variable is required")
        backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")

        chat_enabled_raw = os.environ.get("CHAT_ENABLED", "true").lower()
        chat_enabled = chat_enabled_raw not in ("false", "0", "no")

        chat_max_user_raw = os.environ.get("CHAT_MAX_USER_PER_MIN", "6")
        chat_max_guild_raw = os.environ.get("CHAT_MAX_GUILD_PER_MIN", "60")

        return cls(
            discord_token=token,
            guild_id=int(guild_id_raw),
            sandbox_channel_id=int(sandbox_id_raw),
            backend_url=backend_url.rstrip("/"),
            chat_enabled=chat_enabled,
            chat_max_user_per_min=int(chat_max_user_raw),
            chat_max_guild_per_min=int(chat_max_guild_raw),
        )
