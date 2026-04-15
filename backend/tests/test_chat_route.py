"""Tests for POST /api/chat route (PR 4 — delegates to chat_service.handle).

These are unit-level route tests: chat_service.handle is mocked so the test
stays a pure HTTP layer test (validates schema, routing, field forwarding)
without exercising the full service pipeline.

Settings/schema tests that do not touch chat_service.handle (max-length
enforcement, settings toggle) are retained from PR 1 and still pass because
the Pydantic schema and settings routes are unchanged.
"""

import hashlib
from unittest.mock import AsyncMock, patch

from models.schemas import ChatResponse


def _make_session_id(guild_id: str, channel_id: str, user_id: str) -> str:
    raw = f"{guild_id}|{channel_id}|{user_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _mock_response(
    reply_text: str = "gg, nice question",
    refusal: bool = False,
    provider_used: str = "mock",
    guild_id: str = "33333",
    channel_id: str = "22222",
    user_id: str = "11111",
) -> ChatResponse:
    return ChatResponse(
        reply_text=reply_text,
        session_id=_make_session_id(guild_id, channel_id, user_id),
        refusal=refusal,
        provider_used=provider_used,
    )


# ---------------------------------------------------------------------------
# Route delegation tests
# ---------------------------------------------------------------------------

def test_chat_route_delegates_to_service(client):
    """POST /api/chat calls chat_service.handle with correct fields."""
    expected = _mock_response()
    with patch(
        "services.chat_service.handle",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_handle:
        resp = client.post(
            "/api/chat",
            json={"user_id": "11111", "channel_id": "22222", "guild_id": "33333", "content": "hello"},
        )

    assert resp.status_code == 200
    mock_handle.assert_awaited_once_with(
        user_id="11111",
        channel_id="22222",
        guild_id="33333",
        content="hello",
    )


def test_chat_route_returns_service_response(client):
    """Route forwards chat_service.handle's ChatResponse verbatim."""
    expected = _mock_response(reply_text="locked in", provider_used="openai")
    with patch(
        "services.chat_service.handle",
        new_callable=AsyncMock,
        return_value=expected,
    ):
        resp = client.post(
            "/api/chat",
            json={"user_id": "11111", "channel_id": "22222", "guild_id": "33333", "content": "hey"},
        )

    data = resp.json()
    assert data["reply_text"] == "locked in"
    assert data["provider_used"] == "openai"
    assert data["refusal"] is False
    assert len(data["session_id"]) == 16


def test_chat_route_refusal_forwarded(client):
    """Route forwards refusal=True from chat_service."""
    expected = _mock_response(
        reply_text="lol nah, not doing that. wanna ask about events instead?",
        refusal=True,
    )
    with patch(
        "services.chat_service.handle",
        new_callable=AsyncMock,
        return_value=expected,
    ):
        resp = client.post(
            "/api/chat",
            json={"user_id": "11111", "channel_id": "22222", "guild_id": "33333", "content": "kys"},
        )

    data = resp.json()
    assert data["refusal"] is True
    assert "lol nah" in data["reply_text"]


def test_chat_route_session_id_deterministic(client):
    """Session ID is the same for identical (guild, channel, user) across calls."""
    expected1 = _mock_response()
    expected2 = _mock_response()
    with patch(
        "services.chat_service.handle",
        new_callable=AsyncMock,
        side_effect=[expected1, expected2],
    ):
        r1 = client.post(
            "/api/chat",
            json={"user_id": "11111", "channel_id": "22222", "guild_id": "33333", "content": "ping"},
        )
        r2 = client.post(
            "/api/chat",
            json={"user_id": "11111", "channel_id": "22222", "guild_id": "33333", "content": "pong"},
        )

    assert r1.json()["session_id"] == r2.json()["session_id"]


# ---------------------------------------------------------------------------
# Schema validation tests (no service mock needed — rejected at Pydantic level)
# ---------------------------------------------------------------------------

def test_chat_content_max_length_enforced(client):
    long_content = "x" * 1501
    resp = client.post(
        "/api/chat",
        json={"user_id": "11111", "channel_id": "22222", "guild_id": "33333", "content": long_content},
    )
    assert resp.status_code == 422


def test_chat_content_at_max_length_accepted(client):
    boundary_content = "x" * 1500
    with patch(
        "services.chat_service.handle",
        new_callable=AsyncMock,
        return_value=_mock_response(reply_text="ok"),
    ):
        resp = client.post(
            "/api/chat",
            json={"user_id": "11111", "channel_id": "22222", "guild_id": "33333", "content": boundary_content},
        )
    assert resp.status_code == 200


def test_chat_missing_field_returns_422(client):
    resp = client.post("/api/chat", json={"user_id": "11111", "content": "hi"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Settings tests (settings route is unchanged, no service mock needed)
# ---------------------------------------------------------------------------

def test_chat_settings_get_default(client):
    resp = client.get("/api/settings/chat-enabled")
    assert resp.status_code == 200
    assert resp.json()["chat_enabled"] is False


def test_chat_settings_toggle(client):
    resp = client.post("/api/settings/chat-enabled", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.json()["chat_enabled"] is True

    resp = client.get("/api/settings/chat-enabled")
    assert resp.json()["chat_enabled"] is True

    resp = client.post("/api/settings/chat-enabled", json={"enabled": False})
    assert resp.json()["chat_enabled"] is False
