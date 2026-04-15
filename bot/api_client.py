"""Async HTTP client for the FastAPI backend."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

log = logging.getLogger(__name__)


class BackendClient:
    """Thin wrapper around aiohttp calls to the moderation backend."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session

    # ── internal helpers ──────────────────────────────────────────────

    async def _post(self, path: str, payload: dict[str, Any]) -> dict:
        """POST JSON to *path* and return the parsed response."""
        async with self.session.post(path, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _get(self, path: str) -> dict:
        """GET *path* and return the parsed response."""
        async with self.session.get(path) as resp:
            resp.raise_for_status()
            return await resp.json()

    # ── public API ────────────────────────────────────────────────────

    async def ask_faq(self, question: str) -> dict:
        """Ask the FAQ knowledge base a question."""
        return await self._post("/api/faq/ask", {"question": question})

    async def summarize(self, text: str) -> dict:
        """Summarize an announcement or long text."""
        return await self._post("/api/announcements/summarize", {"text": text})

    async def mod_draft(self, situation: str) -> dict:
        """Draft a moderator response for a given situation."""
        return await self._post("/api/moderation/draft", {"situation": situation})

    async def analyze(self, message_content: str, source: str = "discord") -> dict:
        """Run moderation analysis on a message."""
        return await self._post(
            "/api/moderation/analyze",
            {"message_content": message_content, "source": source},
        )

    async def get_demo_mode(self) -> bool:
        """Return the current demo-mode flag."""
        data = await self._get("/api/settings/demo-mode")
        return data.get("demo_mode", False)

    async def set_demo_mode(self, enabled: bool) -> dict:
        """Toggle demo mode on or off."""
        return await self._post("/api/settings/demo-mode", {"enabled": enabled})

    async def chat(
        self,
        *,
        user_id: str,
        channel_id: str,
        guild_id: str,
        content: str,
    ) -> dict:
        """POST /api/chat — returns {reply_text, session_id, refusal, provider_used}."""
        return await self._post(
            "/api/chat",
            {
                "user_id": user_id,
                "channel_id": channel_id,
                "guild_id": guild_id,
                "content": content,
            },
        )

    async def get_chat_enabled(self) -> bool:
        """GET /api/settings/chat-enabled — return the chat-enabled DB flag."""
        data = await self._get("/api/settings/chat-enabled")
        return data.get("chat_enabled", True)

    async def set_chat_enabled(self, enabled: bool) -> dict:
        """POST /api/settings/chat-enabled — set the chat-enabled DB flag.

        Payload shape matches ChatEnabledRequest from backend/models/schemas.py:
        {"enabled": bool}
        """
        return await self._post("/api/settings/chat-enabled", {"enabled": enabled})
