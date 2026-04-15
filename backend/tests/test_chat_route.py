"""Tests for POST /api/chat echo endpoint (PR 1 — no LLM)."""

import hashlib


def _expected_session_id(guild_id: str, channel_id: str, user_id: str) -> str:
    raw = f"{guild_id}|{channel_id}|{user_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def test_chat_echo_returns_correct_shape(client):
    resp = client.post(
        "/api/chat",
        json={"user_id": "u1", "channel_id": "c1", "guild_id": "g1", "content": "hello world"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply_text"] == "hello world"
    assert data["provider_used"] == "echo"
    assert data["refusal"] is False
    assert len(data["session_id"]) == 16


def test_chat_echo_session_id_deterministic(client):
    payload = {"user_id": "u1", "channel_id": "c1", "guild_id": "g1", "content": "ping"}
    r1 = client.post("/api/chat", json=payload)
    r2 = client.post("/api/chat", json=payload)
    assert r1.json()["session_id"] == r2.json()["session_id"]


def test_chat_echo_session_id_value(client):
    resp = client.post(
        "/api/chat",
        json={"user_id": "u1", "channel_id": "c1", "guild_id": "g1", "content": "test"},
    )
    expected = _expected_session_id("g1", "c1", "u1")
    assert resp.json()["session_id"] == expected


def test_chat_content_max_length_enforced(client):
    long_content = "x" * 1501
    resp = client.post(
        "/api/chat",
        json={"user_id": "u1", "channel_id": "c1", "guild_id": "g1", "content": long_content},
    )
    assert resp.status_code == 422


def test_chat_content_at_max_length_accepted(client):
    boundary_content = "x" * 1500
    resp = client.post(
        "/api/chat",
        json={"user_id": "u1", "channel_id": "c1", "guild_id": "g1", "content": boundary_content},
    )
    assert resp.status_code == 200
    assert resp.json()["reply_text"] == boundary_content


def test_chat_missing_field_returns_422(client):
    # Missing channel_id and guild_id
    resp = client.post("/api/chat", json={"user_id": "u1", "content": "hi"})
    assert resp.status_code == 422


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
