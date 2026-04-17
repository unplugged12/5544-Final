"""Tests for /api/settings/demo-mode endpoints."""


def test_get_demo_mode_default(client):
    """GET /api/settings/demo-mode returns True by default (seeded by init_db)."""
    response = client.get("/api/settings/demo-mode")
    assert response.status_code == 200

    data = response.json()
    assert data["demo_mode"] is True


def test_set_demo_mode_false(client):
    """POST /api/settings/demo-mode can disable demo mode."""
    response = client.post(
        "/api/settings/demo-mode",
        json={"enabled": False},
    )
    assert response.status_code == 200
    assert response.json()["demo_mode"] is False

    # Verify it persisted
    get_resp = client.get("/api/settings/demo-mode")
    assert get_resp.json()["demo_mode"] is False


def test_set_demo_mode_true(client):
    """POST /api/settings/demo-mode can re-enable demo mode."""
    # Disable first
    client.post("/api/settings/demo-mode", json={"enabled": False})

    # Re-enable
    response = client.post(
        "/api/settings/demo-mode",
        json={"enabled": True},
    )
    assert response.status_code == 200
    assert response.json()["demo_mode"] is True


def test_set_demo_mode_toggle_roundtrip(client):
    """Toggling demo mode off then on preserves state correctly."""
    # Default is True
    assert client.get("/api/settings/demo-mode").json()["demo_mode"] is True

    # Toggle off
    client.post("/api/settings/demo-mode", json={"enabled": False})
    assert client.get("/api/settings/demo-mode").json()["demo_mode"] is False

    # Toggle on
    client.post("/api/settings/demo-mode", json={"enabled": True})
    assert client.get("/api/settings/demo-mode").json()["demo_mode"] is True


def test_set_demo_mode_missing_body(client):
    """POST /api/settings/demo-mode with no body returns 422."""
    response = client.post("/api/settings/demo-mode", json={})
    assert response.status_code == 422


def test_demo_mode_response_shape(client):
    """DemoModeResponse contains exactly the demo_mode field."""
    data = client.get("/api/settings/demo-mode").json()
    assert "demo_mode" in data
    assert isinstance(data["demo_mode"], bool)


# ---------------------------------------------------------------------------
# Generic settings CRUD
# ---------------------------------------------------------------------------


def test_get_all_settings_returns_allow_list(client):
    """GET /api/settings surfaces every allow-listed key with seeded defaults."""
    response = client.get("/api/settings")
    assert response.status_code == 200

    settings = response.json()["settings"]
    # Seeded defaults that should be present
    assert settings["demo_mode"] == "true"
    assert settings["test_mode"] == "false"
    assert settings["discipline_points_threshold"] == "5"
    assert settings["discipline_window_days"] == "30"
    assert settings["discipline_repeat_category_kicks"] == "true"
    assert settings["discipline_ban_minutes"] == "60"
    # chat_enabled is seeded on-demand by the /chat-enabled POST, so its key
    # must exist (falls back to "") and never error.
    assert "chat_enabled" in settings


def test_post_settings_updates_multiple_keys(client):
    """POST /api/settings persists a batch of settings and echoes the new state."""
    response = client.post(
        "/api/settings",
        json={
            "updates": {
                "test_mode": "true",
                "discipline_points_threshold": "8",
                "discipline_ban_minutes": "120",
            }
        },
    )
    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["test_mode"] == "true"
    assert settings["discipline_points_threshold"] == "8"
    assert settings["discipline_ban_minutes"] == "120"
    # Untouched keys preserved
    assert settings["demo_mode"] == "true"


def test_post_settings_rejects_unknown_key(client):
    """Keys outside the allow-list are rejected with 422."""
    response = client.post(
        "/api/settings",
        json={"updates": {"OPENAI_API_KEY": "leaked"}},
    )
    assert response.status_code == 422


def test_post_settings_rejects_secret_key(client):
    """Secret keys must never be writeable through the generic endpoint."""
    response = client.post(
        "/api/settings",
        json={"updates": {"DISCORD_TOKEN": "leaked"}},
    )
    assert response.status_code == 422
