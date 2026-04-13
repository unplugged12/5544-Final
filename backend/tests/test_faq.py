"""Tests for POST /api/faq/ask endpoint."""

from unittest.mock import AsyncMock, patch

from providers.base import ProviderResponse
from tests.conftest import MOCK_FAQ_RESPONSE, MOCK_RETRIEVAL_CHUNKS


def test_faq_ask_returns_200(client):
    """POST /api/faq/ask returns 200 with a valid question."""
    with patch(
        "services.provider_service.call",
        new_callable=AsyncMock,
        return_value=MOCK_FAQ_RESPONSE,
    ), patch(
        "services.retrieval_service.retrieve",
        return_value=MOCK_RETRIEVAL_CHUNKS,
    ):
        response = client.post("/api/faq/ask", json={"question": "When is the next tournament?"})

    assert response.status_code == 200


def test_faq_ask_response_shape(client):
    """Response has the TaskResponse shape with expected fields."""
    with patch(
        "services.provider_service.call",
        new_callable=AsyncMock,
        return_value=MOCK_FAQ_RESPONSE,
    ), patch(
        "services.retrieval_service.retrieve",
        return_value=MOCK_RETRIEVAL_CHUNKS,
    ):
        response = client.post("/api/faq/ask", json={"question": "When is the next tournament?"})

    data = response.json()
    assert data["task_type"] == "faq"
    assert "output_text" in data
    assert "citations" in data
    assert isinstance(data["citations"], list)
    assert "confidence_note" in data
    assert "raw_source_ids" in data


def test_faq_ask_includes_citations(client):
    """Response citations match the retrieval chunks used."""
    with patch(
        "services.provider_service.call",
        new_callable=AsyncMock,
        return_value=MOCK_FAQ_RESPONSE,
    ), patch(
        "services.retrieval_service.retrieve",
        return_value=MOCK_RETRIEVAL_CHUNKS,
    ):
        response = client.post("/api/faq/ask", json={"question": "When is the next tournament?"})

    data = response.json()
    assert len(data["citations"]) == 1
    assert data["citations"][0]["source_id"] == "faq_001"
    assert data["citations"][0]["citation_label"] == "FAQ: Tournament Schedule"


def test_faq_ask_extracts_confidence(client):
    """The confidence note is parsed from the LLM response."""
    with patch(
        "services.provider_service.call",
        new_callable=AsyncMock,
        return_value=MOCK_FAQ_RESPONSE,
    ), patch(
        "services.retrieval_service.retrieve",
        return_value=MOCK_RETRIEVAL_CHUNKS,
    ):
        response = client.post("/api/faq/ask", json={"question": "When is the next tournament?"})

    data = response.json()
    assert data["confidence_note"] is not None
    assert "High" in data["confidence_note"]


def test_faq_ask_returns_raw_source_ids(client):
    """raw_source_ids lists the source_ids from retrieval."""
    with patch(
        "services.provider_service.call",
        new_callable=AsyncMock,
        return_value=MOCK_FAQ_RESPONSE,
    ), patch(
        "services.retrieval_service.retrieve",
        return_value=MOCK_RETRIEVAL_CHUNKS,
    ):
        response = client.post("/api/faq/ask", json={"question": "When is the next tournament?"})

    data = response.json()
    assert "faq_001" in data["raw_source_ids"]


def test_faq_ask_empty_question_rejected(client):
    """POST /api/faq/ask with empty body returns 422."""
    response = client.post("/api/faq/ask", json={})
    assert response.status_code == 422


def test_faq_ask_with_mock_returning_known_answer(client):
    """Mock provider returns a specific answer and we verify it passes through."""
    custom_response = ProviderResponse(
        text="You can sign up in #tournament-signup.\n\nConfidence: Moderate - Based on FAQ data.",
        provider_name="mock",
        model="mock-model",
        usage={},
    )

    with patch(
        "services.provider_service.call",
        new_callable=AsyncMock,
        return_value=custom_response,
    ), patch(
        "services.retrieval_service.retrieve",
        return_value=MOCK_RETRIEVAL_CHUNKS,
    ):
        response = client.post("/api/faq/ask", json={"question": "How do I sign up?"})

    data = response.json()
    assert "tournament-signup" in data["output_text"]
    assert "Moderate" in data["confidence_note"]
