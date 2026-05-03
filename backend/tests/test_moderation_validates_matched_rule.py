"""Verify analyze() rejects matched_rule values not in rules.json."""

from __future__ import annotations

import json

from unittest.mock import AsyncMock, patch

import pytest

from models.enums import EventSource, ModerationStatus, ViolationType
from models.schemas import ModerationEventResponse
from providers.base import ProviderResponse
from tests.conftest import MOCK_RETRIEVAL_CHUNKS


def _hallucinated_rule_response() -> ProviderResponse:
    return ProviderResponse(
        text=json.dumps(
            {
                "violation_type": "harassment",
                "matched_rule": "Rule 99: Pretend",
                "explanation": "LLM made this rule up.",
                "severity": "high",
                "suggested_action": "remove_message",
                "confidence_note": "High - clear",
            }
        ),
        provider_name="mock",
        model="mock-model",
        usage={},
    )


@pytest.mark.anyio
async def test_analyze_nulls_unknown_matched_rule(db_path):
    """When the LLM returns a rule label that isn't in rules.json, the persisted
    event must have matched_rule=None (and a warning is logged)."""
    captured_kwargs: dict = {}

    async def _capture_create(**kwargs):
        captured_kwargs.update(kwargs)
        return ModerationEventResponse(
            event_id=kwargs["event_id"],
            message_content=kwargs["message_content"],
            violation_type=kwargs["violation_type"],
            matched_rule=kwargs["matched_rule"],
            explanation=kwargs["explanation"],
            severity=kwargs["severity"],
            suggested_action=kwargs["suggested_action"],
            status=kwargs["status"],
            source=kwargs["source"],
            created_at="2026-01-01 00:00:00",
        )

    with (
        patch("config.settings.SQLITE_PATH", db_path),
        patch(
            "services.provider_service.call",
            new_callable=AsyncMock,
            return_value=_hallucinated_rule_response(),
        ),
        patch(
            "services.retrieval_service.retrieve_split",
            return_value=MOCK_RETRIEVAL_CHUNKS,
        ),
        patch(
            "repositories.moderation_repo.create",
            new=AsyncMock(side_effect=_capture_create),
        ),
        patch("services.audit_service.log_interaction", new_callable=AsyncMock),
        patch(
            "repositories.settings_repo.get_demo_mode",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        from services import moderation_service

        result = await moderation_service.analyze(
            "you are trash", EventSource.DASHBOARD
        )

    # Persisted event got the nulled matched_rule
    assert captured_kwargs["matched_rule"] is None
    assert captured_kwargs["violation_type"] == ViolationType.HARASSMENT
    # Returned event reflects the nulled value too
    assert result.matched_rule is None
    # Sanity: status is pending because demo_mode=False
    assert result.status == ModerationStatus.PENDING
