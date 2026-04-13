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
