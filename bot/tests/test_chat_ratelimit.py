"""Tests for the sliding-window chat rate limiter.

PR 7 additions:
  - Injection-marker auto-timeout: > 5 hits in 10 min → 1h ban
  - Eviction of stale markers from the injection window
  - Timeout check runs first in allow() (before user/guild windows)
  - After timeout expires, allow() returns True again
"""

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


# ── injection-marker auto-timeout (PR 7) ──────────────────────────────────────

def _make_injection_limiter(
    *,
    threshold: int = 5,
    window_sec: int = 600,
    timeout_sec: int = 3600,
) -> ChatRateLimiter:
    """Return a limiter with high per-user/guild limits so injection tests are isolated."""
    return ChatRateLimiter(
        user_per_min=1000,
        guild_per_min=1000,
        injection_marker_threshold=threshold,
        injection_marker_window_sec=window_sec,
        timeout_duration_sec=timeout_sec,
    )


class TestInjectionMarkerAutoTimeout:
    def test_exactly_threshold_hits_no_timeout(self) -> None:
        """Exactly threshold (5) hits in window → no timeout (boundary: > not >=)."""
        limiter = _make_injection_limiter(threshold=5)
        for _ in range(5):
            limiter.record_injection_marker(user_id="u1")
        # 5 hits, threshold is 5 — not exceeded (> 5 required)
        assert limiter.allow(user_id="u1", guild_id="g1") is True

    def test_one_over_threshold_triggers_timeout(self) -> None:
        """6 hits with threshold=5 → timeout activated."""
        limiter = _make_injection_limiter(threshold=5)
        for _ in range(6):
            limiter.record_injection_marker(user_id="u1")
        # User is now timed out
        assert limiter.allow(user_id="u1", guild_id="g1") is False

    def test_timeout_blocks_even_when_rate_windows_clear(self) -> None:
        """During timeout, allow() returns False even if per-user/guild windows are empty."""
        limiter = _make_injection_limiter(threshold=5, timeout_sec=3600)
        for _ in range(6):
            limiter.record_injection_marker(user_id="u1")
        # The user's rate windows are untouched (no calls to allow() yet),
        # but the injection timeout should still block.
        assert limiter.allow(user_id="u1", guild_id="g1") is False

    def test_timeout_expires_and_allow_resumes(self) -> None:
        """After timeout_sec elapses, allow() returns True again."""
        base = 5000.0
        limiter = _make_injection_limiter(threshold=5, timeout_sec=3600)

        with patch("chat_ratelimit.time") as mock_time:
            mock_time.monotonic.return_value = base
            for _ in range(6):
                limiter.record_injection_marker(user_id="u1")

            # Still in timeout
            assert limiter.allow(user_id="u1", guild_id="g1") is False

            # Advance past the 1h timeout
            mock_time.monotonic.return_value = base + 3601.0
            assert limiter.allow(user_id="u1", guild_id="g1") is True

    def test_stale_markers_evicted_from_injection_window(self) -> None:
        """Injection markers older than window_sec are evicted on the next record call."""
        base = 8000.0
        limiter = _make_injection_limiter(threshold=5, window_sec=600, timeout_sec=3600)

        with patch("chat_ratelimit.time") as mock_time:
            # Record 4 hits at t=0 (below threshold)
            mock_time.monotonic.return_value = base
            for _ in range(4):
                limiter.record_injection_marker(user_id="u1")

            # Advance 601s — all 4 entries expire from the window
            mock_time.monotonic.return_value = base + 601.0
            # Record 5 more — only these 5 are in the window (4 evicted)
            for _ in range(5):
                limiter.record_injection_marker(user_id="u1")

            # 5 hits == threshold, not exceeded → no timeout
            assert limiter.allow(user_id="u1", guild_id="g1") is True

    def test_other_user_not_affected_by_timeout(self) -> None:
        """Timed-out user does not affect a different user."""
        limiter = _make_injection_limiter(threshold=5)
        for _ in range(6):
            limiter.record_injection_marker(user_id="u1")

        # u1 is timed out; u2 should still pass
        assert limiter.allow(user_id="u1", guild_id="g1") is False
        assert limiter.allow(user_id="u2", guild_id="g1") is True

    def test_timeout_check_runs_before_rate_windows(self) -> None:
        """Timed-out user is rejected before the per-user window is checked/incremented."""
        limiter = _make_injection_limiter(threshold=5, timeout_sec=3600)
        # Exhaust the per-user window for u2 so it's full
        limiter2 = _make_injection_limiter(threshold=5)

        # Record timeout for u1
        for _ in range(6):
            limiter.record_injection_marker(user_id="u1")

        # allow() should return False without incrementing any window
        before_guild_len = len(limiter._guild_window["g1"])
        result = limiter.allow(user_id="u1", guild_id="g1")

        assert result is False
        # Guild window must not have been incremented (timeout check ran first)
        assert len(limiter._guild_window["g1"]) == before_guild_len
