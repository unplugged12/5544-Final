"""Tests for /api/moderation/* and /api/history endpoints."""

import json

from unittest.mock import AsyncMock, patch

from providers.base import ProviderResponse
from tests.conftest import MOCK_MODERATION_RESPONSE, MOCK_RETRIEVAL_CHUNKS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _analyze(client, message: str = "you're garbage uninstall"):
    """Call POST /api/moderation/analyze with mocked provider + retrieval."""
    with patch(
        "services.provider_service.call",
        new_callable=AsyncMock,
        return_value=MOCK_MODERATION_RESPONSE,
    ), patch(
        "services.retrieval_service.retrieve",
        return_value=MOCK_RETRIEVAL_CHUNKS,
    ):
        return client.post(
            "/api/moderation/analyze",
            json={"message_content": message},
        )


# ---------------------------------------------------------------------------
# POST /api/moderation/analyze
# ---------------------------------------------------------------------------

def test_analyze_returns_200(client):
    """POST /api/moderation/analyze returns 200."""
    response = _analyze(client)
    assert response.status_code == 200


def test_analyze_response_shape(client):
    """Response matches ModerationEventResponse shape."""
    data = _analyze(client).json()

    expected_fields = {
        "event_id",
        "message_content",
        "violation_type",
        "matched_rule",
        "explanation",
        "severity",
        "suggested_action",
        "status",
        "source",
        "created_at",
    }
    assert expected_fields.issubset(set(data.keys()))


def test_analyze_returns_correct_violation(client):
    """Mocked provider yields the expected violation type and severity."""
    data = _analyze(client).json()

    assert data["violation_type"] == "harassment"
    assert data["severity"] == "high"
    assert data["suggested_action"] == "remove_message"
    assert data["matched_rule"] == "Rule 1: No Harassment or Bullying"


def test_analyze_auto_actions_in_demo_mode(client):
    """In demo mode, high-severity remove_message is auto-actioned."""
    data = _analyze(client).json()

    # Demo mode is seeded as True by init_db, and suggested_action is
    # remove_message which is in the auto-action set.
    assert data["status"] == "auto_actioned"


def test_analyze_persists_event(client):
    """The created event can be fetched from history."""
    _analyze(client)

    history = client.get("/api/history").json()
    assert history["total"] >= 1
    assert any(
        e["violation_type"] == "harassment" for e in history["events"]
    )


def test_analyze_missing_body(client):
    """POST /api/moderation/analyze with no body returns 422."""
    response = client.post("/api/moderation/analyze", json={})
    assert response.status_code == 422


def test_analyze_source_defaults_to_dashboard(client):
    """When source is omitted, it defaults to 'dashboard'."""
    data = _analyze(client).json()
    assert data["source"] == "dashboard"


# ---------------------------------------------------------------------------
# POST /api/moderation/approve/{id}
# ---------------------------------------------------------------------------

def test_approve_changes_status(client):
    """Approving an event sets status to 'approved'."""
    event_id = _analyze(client).json()["event_id"]

    response = client.post(f"/api/moderation/approve/{event_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "approved"
    assert data["resolved_by"] == "dashboard"
    assert data["resolved_at"] is not None


def test_approve_nonexistent_returns_404(client):
    """Approving a non-existent event returns 404."""
    response = client.post("/api/moderation/approve/does_not_exist")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/moderation/reject/{id}
# ---------------------------------------------------------------------------

def test_reject_changes_status(client):
    """Rejecting an event sets status to 'rejected'."""
    event_id = _analyze(client).json()["event_id"]

    response = client.post(f"/api/moderation/reject/{event_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "rejected"
    assert data["resolved_by"] == "dashboard"
    assert data["resolved_at"] is not None


def test_reject_nonexistent_returns_404(client):
    """Rejecting a non-existent event returns 404."""
    response = client.post("/api/moderation/reject/does_not_exist")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/history
# ---------------------------------------------------------------------------

def test_history_empty(client):
    """GET /api/history returns empty list when no events exist."""
    response = client.get("/api/history")
    assert response.status_code == 200

    data = response.json()
    assert data["events"] == []
    assert data["total"] == 0


def test_history_returns_events(client):
    """GET /api/history returns events after analysis."""
    _analyze(client)
    _analyze(client, message="another toxic message")

    response = client.get("/api/history")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 2
    assert len(data["events"]) == 2


def test_history_response_shape(client):
    """History response has events list and total."""
    data = client.get("/api/history").json()
    assert "events" in data
    assert "total" in data
    assert isinstance(data["events"], list)
    assert isinstance(data["total"], int)


# ---------------------------------------------------------------------------
# Moderation with a low-severity / no-action response (stays pending)
# ---------------------------------------------------------------------------

def test_analyze_low_severity_stays_pending(client):
    """A no_action suggestion stays pending even in demo mode."""
    low_severity_response = ProviderResponse(
        text=json.dumps(
            {
                "violation_type": "no_violation",
                "matched_rule": None,
                "explanation": "No violation detected.",
                "severity": "low",
                "suggested_action": "no_action",
                "confidence_note": "High",
            }
        ),
        provider_name="mock",
        model="mock-model",
        usage={},
    )

    with patch(
        "services.provider_service.call",
        new_callable=AsyncMock,
        return_value=low_severity_response,
    ), patch(
        "services.retrieval_service.retrieve",
        return_value=MOCK_RETRIEVAL_CHUNKS,
    ):
        response = client.post(
            "/api/moderation/analyze",
            json={"message_content": "gg nice game everyone"},
        )

    data = response.json()
    assert data["status"] == "pending"
    assert data["violation_type"] == "no_violation"
