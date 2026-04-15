"""Tests for ChatRequest field validator — CHAT_INPUT_MAX_CHARS honoured."""

import pytest
from pydantic import ValidationError
from unittest.mock import patch


_BASE = {"user_id": "u1", "channel_id": "c1", "guild_id": "g1"}


def _make(**kwargs):
    from models.schemas import ChatRequest

    return ChatRequest(**{**_BASE, **kwargs})


def test_default_limit_accepts_1500_chars():
    """1 500-char payload passes with the default CHAT_INPUT_MAX_CHARS=1500."""
    req = _make(content="x" * 1500)
    assert len(req.content) == 1500


def test_default_limit_rejects_1501_chars():
    """1 501-char payload fails with the default CHAT_INPUT_MAX_CHARS=1500."""
    with pytest.raises(ValidationError):
        _make(content="x" * 1501)


def test_custom_limit_respected():
    """Monkey-patching CHAT_INPUT_MAX_CHARS=10 blocks content longer than 10."""
    with patch("config.settings.CHAT_INPUT_MAX_CHARS", 10):
        with pytest.raises(ValidationError):
            _make(content="x" * 11)


def test_custom_limit_allows_at_boundary():
    """Exactly at the custom limit (10 chars) is accepted."""
    with patch("config.settings.CHAT_INPUT_MAX_CHARS", 10):
        req = _make(content="x" * 10)
        assert len(req.content) == 10
