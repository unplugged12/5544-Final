"""Tests for GET /api/health endpoint."""


def test_health_returns_200(client):
    """GET /api/health should return 200 with status 'ok'."""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"


def test_health_response_shape(client):
    """Health response includes all expected fields."""
    data = client.get("/api/health").json()

    assert "status" in data
    assert "demo_mode" in data
    assert "provider" in data
    assert "knowledge_count" in data
    assert isinstance(data["demo_mode"], bool)
    assert isinstance(data["knowledge_count"], int)
