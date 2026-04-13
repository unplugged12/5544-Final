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
