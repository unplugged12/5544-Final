"""Tests for moderation_service.classify_only and the _run_moderation_llm refactor.

Verifies:
  - classify_only returns ModerationLLMResult with same shape as the LLM result level
  - classify_only does NOT call moderation_repo.create
  - classify_only does NOT call audit_service.log_interaction
  - analyze still calls both moderation_repo.create and audit_service.log_interaction
    (regression — proves the refactor did not break analyze's persistence behaviour)
"""

import json
import pytest

from unittest.mock import AsyncMock, patch

from models.enums import EventSource, Severity, ViolationType
from providers.base import ProviderResponse
from services.moderation_service import ModerationLLMResult
from tests.conftest import MOCK_MODERATION_RESPONSE, MOCK_RETRIEVAL_CHUNKS


def _make_provider_resp(severity: str = "high", violation: str = "harassment") -> ProviderResponse:
    return ProviderResponse(
        text=json.dumps({
            "violation_type": violation,
            "matched_rule": "Rule 1: No Harassment or Bullying",
            "explanation": "Test explanation.",
            "severity": severity,
            "suggested_action": "remove_message",
            "confidence_note": "High",
        }),
        provider_name="mock",
        model="mock-model",
        usage={},
    )


# ---------------------------------------------------------------------------
# classify_only — shape and no-persistence contract
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_classify_only_returns_moderation_llm_result():
    """classify_only returns a ModerationLLMResult dataclass."""
    with (
        patch("services.provider_service.call", new_callable=AsyncMock, return_value=_make_provider_resp()),
        patch("services.retrieval_service.retrieve", return_value=MOCK_RETRIEVAL_CHUNKS),
    ):
        from services import moderation_service
        result = await moderation_service.classify_only("you are trash")

    assert isinstance(result, ModerationLLMResult)
    assert result.violation_type == ViolationType.HARASSMENT
    assert result.severity == Severity.HIGH
    assert result.explanation == "Test explanation."
    assert result.provider_name == "mock"


@pytest.mark.anyio
async def test_classify_only_does_not_call_moderation_repo_create():
    """classify_only must NOT persist a moderation_events row."""
    with (
        patch("services.provider_service.call", new_callable=AsyncMock, return_value=_make_provider_resp()),
        patch("services.retrieval_service.retrieve", return_value=MOCK_RETRIEVAL_CHUNKS),
        patch("repositories.moderation_repo.create", new_callable=AsyncMock) as mock_create,
    ):
        from services import moderation_service
        await moderation_service.classify_only("test text")

    mock_create.assert_not_called()


@pytest.mark.anyio
async def test_classify_only_does_not_call_audit_log_interaction():
    """classify_only must NOT write to interaction_history."""
    with (
        patch("services.provider_service.call", new_callable=AsyncMock, return_value=_make_provider_resp()),
        patch("services.retrieval_service.retrieve", return_value=MOCK_RETRIEVAL_CHUNKS),
        patch("services.audit_service.log_interaction", new_callable=AsyncMock) as mock_audit,
    ):
        from services import moderation_service
        await moderation_service.classify_only("test text")

    mock_audit.assert_not_called()


@pytest.mark.anyio
async def test_classify_only_no_violation_parse():
    """classify_only correctly parses a no_violation response."""
    no_violation_resp = ProviderResponse(
        text=json.dumps({
            "violation_type": "no_violation",
            "matched_rule": None,
            "explanation": "No violation.",
            "severity": "low",
            "suggested_action": "no_action",
            "confidence_note": "High",
        }),
        provider_name="mock",
        model="mock-model",
        usage={},
    )
    with (
        patch("services.provider_service.call", new_callable=AsyncMock, return_value=no_violation_resp),
        patch("services.retrieval_service.retrieve", return_value=MOCK_RETRIEVAL_CHUNKS),
    ):
        from services import moderation_service
        result = await moderation_service.classify_only("gg nice game")

    assert result.violation_type == ViolationType.NO_VIOLATION
    assert result.severity == Severity.LOW


# ---------------------------------------------------------------------------
# analyze — regression: persistence contract must be unchanged
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_analyze_still_calls_moderation_repo_create(db_path):
    """analyze must still persist a moderation_events row after the refactor."""
    with (
        patch("config.settings.SQLITE_PATH", db_path),
        patch("services.provider_service.call", new_callable=AsyncMock, return_value=MOCK_MODERATION_RESPONSE),
        patch("services.retrieval_service.retrieve", return_value=MOCK_RETRIEVAL_CHUNKS),
        patch("repositories.moderation_repo.create", new_callable=AsyncMock) as mock_create,
        patch("services.audit_service.log_interaction", new_callable=AsyncMock),
        patch("repositories.settings_repo.get_demo_mode", new_callable=AsyncMock, return_value=False),
    ):
        from services import moderation_service
        await moderation_service.analyze("you are trash", EventSource.DASHBOARD)

    mock_create.assert_awaited_once()


@pytest.mark.anyio
async def test_analyze_still_calls_audit_log_interaction(db_path):
    """analyze must still write to interaction_history after the refactor."""
    with (
        patch("config.settings.SQLITE_PATH", db_path),
        patch("services.provider_service.call", new_callable=AsyncMock, return_value=MOCK_MODERATION_RESPONSE),
        patch("services.retrieval_service.retrieve", return_value=MOCK_RETRIEVAL_CHUNKS),
        patch("repositories.moderation_repo.create", new_callable=AsyncMock),
        patch("services.audit_service.log_interaction", new_callable=AsyncMock) as mock_audit,
        patch("repositories.settings_repo.get_demo_mode", new_callable=AsyncMock, return_value=False),
    ):
        from services import moderation_service
        await moderation_service.analyze("you are trash", EventSource.DASHBOARD)

    mock_audit.assert_awaited_once()
    _, kwargs = mock_audit.call_args
    assert kwargs["task_type"] == "moderation"


@pytest.mark.anyio
async def test_analyze_returns_moderation_event_response(db_path):
    """analyze still returns a ModerationEventResponse (public API unchanged)."""
    from models.schemas import ModerationEventResponse

    with (
        patch("config.settings.SQLITE_PATH", db_path),
        patch("services.provider_service.call", new_callable=AsyncMock, return_value=MOCK_MODERATION_RESPONSE),
        patch("services.retrieval_service.retrieve", return_value=MOCK_RETRIEVAL_CHUNKS),
        patch("repositories.moderation_repo.create", new_callable=AsyncMock, return_value=ModerationEventResponse(
            event_id="test_id",
            message_content="you are trash",
            violation_type=ViolationType.HARASSMENT,
            matched_rule="Rule 1",
            explanation="Harassment",
            severity=Severity.HIGH,
            suggested_action="remove_message",
            status="pending",
            source=EventSource.DASHBOARD,
            created_at="2026-01-01 00:00:00",
        )),
        patch("services.audit_service.log_interaction", new_callable=AsyncMock),
        patch("repositories.settings_repo.get_demo_mode", new_callable=AsyncMock, return_value=False),
    ):
        from services import moderation_service
        result = await moderation_service.analyze("you are trash", EventSource.DASHBOARD)

    assert isinstance(result, ModerationEventResponse)
