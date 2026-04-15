"""Sliding-window rate limiter for chat triggers.

PR 7 adds injection-marker auto-timeout: if a single user triggers
contains_prompt_injection_markers more than `injection_marker_threshold` times
in `injection_marker_window_sec` seconds, they are banned for
`timeout_duration_sec` seconds (default: 1h).

The ban check runs FIRST in allow() so a banned user is rejected immediately
even if their per-user / per-guild windows would otherwise have capacity.

All state is in-memory and resets on bot restart — sufficient for v1. A
persistent quota store is left for a future PR if operational requirements
change.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

log = logging.getLogger(__name__)


class ChatRateLimiter:
    """
    Sliding-window rate limiter for chat triggers.

    Per-user:  N triggers per 60s
    Per-guild: M triggers per 60s

    PR 7: injection-marker auto-timeout
      > injection_marker_threshold hits in injection_marker_window_sec
      → user banned for timeout_duration_sec

    Uses time.monotonic for clock skew safety. Memory-only (resets on bot
    restart) — sufficient for v1; persistent quota tracking is a future PR.

    Semantics: a trigger is only "spent" if it is accepted. If the guild
    window is full, neither the guild nor the user counter is incremented.
    If the guild window has room but the user window is full, neither counter
    is incremented. Both windows record the same trigger timestamp only when
    allow() returns True.
    """

    def __init__(
        self,
        *,
        user_per_min: int,
        guild_per_min: int,
        injection_marker_threshold: int = 5,
        injection_marker_window_sec: int = 600,  # 10 minutes
        timeout_duration_sec: int = 3600,  # 1 hour
    ) -> None:
        self.user_limit = user_per_min
        self.guild_limit = guild_per_min
        self.injection_marker_threshold = injection_marker_threshold
        self.injection_marker_window_sec = injection_marker_window_sec
        self.timeout_duration_sec = timeout_duration_sec

        self._user_window: dict[str, deque[float]] = defaultdict(deque)
        self._guild_window: dict[str, deque[float]] = defaultdict(deque)

        # PR 7: injection-marker tracking
        self._user_injection_window: dict[str, deque[float]] = defaultdict(deque)
        self._user_timeout_until: dict[str, float] = {}

    def record_injection_marker(self, *, user_id: str) -> None:
        """Record one injection-marker hit for user_id.

        Called by the chat cog when the backend response indicates
        injection_marker_seen=True. If the user exceeds
        injection_marker_threshold hits within injection_marker_window_sec,
        they are timed out for timeout_duration_sec.

        The threshold is > N (i.e., N+1 hits triggers the ban), matching the
        spec: "more than 5 injection-marker hits in 10 min → 1h ban".
        Entries older than the window are evicted on each call.
        """
        now = time.monotonic()
        cutoff = now - self.injection_marker_window_sec
        window = self._user_injection_window[user_id]

        # Evict expired entries
        while window and window[0] < cutoff:
            window.popleft()

        window.append(now)

        if len(window) > self.injection_marker_threshold:
            self._user_timeout_until[user_id] = now + self.timeout_duration_sec
            log.warning(
                "chat: user %s timed out for %ds — injection marker threshold exceeded (%d hits in %ds window)",
                user_id,
                self.timeout_duration_sec,
                len(window),
                self.injection_marker_window_sec,
            )

    def allow(self, *, user_id: str, guild_id: str) -> bool:
        """Return True if the trigger should be allowed; False to drop.

        Check order (fail-fast):
          1. Injection-marker timeout (most targeted — checked first)
          2. Per-guild limit (global flood protection)
          3. Per-user limit

        Counters are only incremented when the trigger is accepted.
        """
        now = time.monotonic()

        # 1. Check injection-marker timeout
        timeout_until = self._user_timeout_until.get(user_id, 0.0)
        if timeout_until > now:
            return False

        cutoff = now - 60.0

        # 2. Check & evict per-guild (fail fast on global flood)
        gw = self._guild_window[guild_id]
        while gw and gw[0] < cutoff:
            gw.popleft()
        if len(gw) >= self.guild_limit:
            return False

        # 3. Check & evict per-user
        uw = self._user_window[user_id]
        while uw and uw[0] < cutoff:
            uw.popleft()
        if len(uw) >= self.user_limit:
            return False

        # Accept: record trigger in both windows
        gw.append(now)
        uw.append(now)
        return True
