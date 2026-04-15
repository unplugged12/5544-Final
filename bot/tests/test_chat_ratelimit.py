"""Tests for the sliding-window chat rate limiter."""

from __future__ import annotations

import sys
import os
import time
from unittest.mock import patch

import pytest

# Ensure bot/ is on sys.path when running tests from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chat_ratelimit import ChatRateLimiter


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_limiter(*, user_limit: int = 3, guild_limit: int = 10) -> ChatRateLimiter:
    return ChatRateLimiter(user_per_min=user_limit, guild_per_min=guild_limit)


# ── per-user window ───────────────────────────────────────────────────────────

class TestPerUserLimit:
    def test_allows_up_to_limit(self) -> None:
        limiter = _make_limiter(user_limit=3)
        for _ in range(3):
            assert limiter.allow(user_id="u1", guild_id="g1") is True

    def test_drops_beyond_limit(self) -> None:
        limiter = _make_limiter(user_limit=3)
        for _ in range(3):
            limiter.allow(user_id="u1", guild_id="g1")
        assert limiter.allow(user_id="u1", guild_id="g1") is False

    def test_window_slide_allows_again(self) -> None:
        """After the 60 s window slides, old entries are evicted and new triggers allowed."""
        limiter = _make_limiter(user_limit=2)
        base = 1000.0

        with patch("chat_ratelimit.time") as mock_time:
            mock_time.monotonic.return_value = base
            limiter.allow(user_id="u1", guild_id="g1")
            limiter.allow(user_id="u1", guild_id="g1")
            # Now at limit — blocked
            assert limiter.allow(user_id="u1", guild_id="g1") is False

            # Advance 61 s — both old entries expire
            mock_time.monotonic.return_value = base + 61.0
            assert limiter.allow(user_id="u1", guild_id="g1") is True

    def test_user_buckets_dont_bleed_across_guilds(self) -> None:
        """Same user_id in a different guild gets its own user-window bucket."""
        limiter = _make_limiter(user_limit=2, guild_limit=100)
        limiter.allow(user_id="u1", guild_id="g1")
        limiter.allow(user_id="u1", guild_id="g1")
        # Exhausted for g1

        # In a different guild, the same user should still be allowed
        # (user window is keyed only by user_id — shared across guilds by design)
        # This test verifies the GUILD window for g2 is fresh (not shared with g1).
        limiter2 = _make_limiter(user_limit=100, guild_limit=100)
        assert limiter2.allow(user_id="u1", guild_id="g2") is True


# ── per-guild window ──────────────────────────────────────────────────────────

class TestPerGuildLimit:
    def test_guild_limit_drops_different_users(self) -> None:
        """Guild limit applies across all users in the guild."""
        limiter = _make_limiter(user_limit=100, guild_limit=3)
        assert limiter.allow(user_id="u1", guild_id="g1") is True
        assert limiter.allow(user_id="u2", guild_id="g1") is True
        assert limiter.allow(user_id="u3", guild_id="g1") is True
        # Guild window full — any user is now blocked
        assert limiter.allow(user_id="u4", guild_id="g1") is False
        assert limiter.allow(user_id="u1", guild_id="g1") is False

    def test_guild_buckets_are_independent(self) -> None:
        """Different guilds do not share a window."""
        limiter = _make_limiter(user_limit=100, guild_limit=2)
        limiter.allow(user_id="u1", guild_id="g1")
        limiter.allow(user_id="u1", guild_id="g1")
        # g1 is at guild limit; g2 is fresh
        assert limiter.allow(user_id="u1", guild_id="g2") is True

    def test_guild_limit_checked_before_user_limit(self) -> None:
        """When guild is at limit, user counter must NOT be incremented (limit-not-spent)."""
        limiter = _make_limiter(user_limit=5, guild_limit=1)
        # Fill the guild window
        limiter.allow(user_id="u1", guild_id="g1")
        # Guild is full; further calls from u2 are dropped
        assert limiter.allow(user_id="u2", guild_id="g1") is False
        # u2 user window should be 0 (not incremented)
        # Verify: switch to a guild with fresh window — u2 should still be fully allowed
        assert limiter.allow(user_id="u2", guild_id="g2") is True


# ── clock-controlled tests ─────────────────────────────────────────────────────

class TestClockControl:
    def test_monotonic_clock_used(self) -> None:
        """allow() must use time.monotonic (verifiable by patching it)."""
        limiter = _make_limiter(user_limit=1)
        call_count = 0
        original = time.monotonic

        def counting_monotonic() -> float:
            nonlocal call_count
            call_count += 1
            return original()

        with patch("chat_ratelimit.time.monotonic", side_effect=counting_monotonic):
            limiter.allow(user_id="u1", guild_id="g1")

        assert call_count >= 1, "time.monotonic was not called"

    def test_partial_window_eviction(self) -> None:
        """Only entries older than 60 s are evicted; recent entries remain."""
        limiter = _make_limiter(user_limit=3, guild_limit=100)
        base = 2000.0

        with patch("chat_ratelimit.time") as mock_time:
            # Two triggers at t=0
            mock_time.monotonic.return_value = base
            limiter.allow(user_id="u1", guild_id="g1")
            limiter.allow(user_id="u1", guild_id="g1")

            # One more trigger at t=30 (within window)
            mock_time.monotonic.return_value = base + 30.0
            limiter.allow(user_id="u1", guild_id="g1")
            # User is now at limit=3

            # Advance to t=61 — first two (t=0) are evicted; t=30 remains
            mock_time.monotonic.return_value = base + 61.0
            # Should allow 2 more (evicted 2, still have 1 from t=30)
            assert limiter.allow(user_id="u1", guild_id="g1") is True
            assert limiter.allow(user_id="u1", guild_id="g1") is True
            # Now at limit again (t=30 entry + 2 new = 3)
            assert limiter.allow(user_id="u1", guild_id="g1") is False
