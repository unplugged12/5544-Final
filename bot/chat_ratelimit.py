"""Sliding-window rate limiter for chat triggers."""

from __future__ import annotations

import time
from collections import defaultdict, deque


class ChatRateLimiter:
    """
    Sliding-window rate limiter for chat triggers.

    Per-user:  N triggers per 60s
    Per-guild: M triggers per 60s

    Uses time.monotonic for clock skew safety. Memory-only (resets on bot
    restart) — sufficient for v1; persistent quota tracking is PR 7 territory.

    Semantics: a trigger is only "spent" if it is accepted. If the guild
    window is full, neither the guild nor the user counter is incremented.
    If the guild window has room but the user window is full, neither counter
    is incremented. Both windows record the same trigger timestamp only when
    allow() returns True.
    """

    def __init__(self, *, user_per_min: int, guild_per_min: int) -> None:
        self.user_limit = user_per_min
        self.guild_limit = guild_per_min
        self._user_window: dict[str, deque[float]] = defaultdict(deque)
        self._guild_window: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, *, user_id: str, guild_id: str) -> bool:
        """Return True if the trigger should be allowed; False to drop.

        Per-guild check runs first (cheaper fail-fast on a global flood).
        Counters are only incremented when the trigger is accepted.
        """
        now = time.monotonic()
        cutoff = now - 60.0

        # Check & evict per-guild (fail fast on global flood)
        gw = self._guild_window[guild_id]
        while gw and gw[0] < cutoff:
            gw.popleft()
        if len(gw) >= self.guild_limit:
            return False

        # Check & evict per-user
        uw = self._user_window[user_id]
        while uw and uw[0] < cutoff:
            uw.popleft()
        if len(uw) >= self.user_limit:
            return False

        # Accept: record trigger in both windows
        gw.append(now)
        uw.append(now)
        return True
