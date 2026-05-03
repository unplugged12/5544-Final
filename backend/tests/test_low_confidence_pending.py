"""Verify the demo-mode confidence gate.

Per the user's posture: only "Low" confidence downgrades an auto-action
suggestion to PENDING. "High" and "Moderate" continue to AUTO_ACTIONED.
"""

from __future__ import annotations

import json

from unittest.mock import AsyncMock, patch

import pytest

from models.enums import EventSource, ModerationStatus
from models.schemas import ModerationEventResponse
from providers.base import ProviderResponse
from tests.conftest import MOCK_RETRIEVAL_CHUNKS


def _moderation_response(confidence_note: str) -> ProviderResponse:
    return ProviderResponse(
        text=json.dumps(
            {
                "violation_type": "harassment",
                "matched_rule": "Rule 1: No Harassment or Bullying",
                "explanation": "Borderline harassment.",
                "severity": "high",
                "suggested_action": "remove_message",
                "confidence_note": confidence_note,
            }
        ),
        provider_name="mock",
        model="mock-model",
        usage={},
    )


def _make_capture():
    """Return (capture_dict, async_create_fn) — repo.create returns a real
    ModerationEventResponse so analyze() can model_copy it."""
    captured: dict = {}

    async def _capture(**kwargs):
        captured.update(kwargs)
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

    return captured, _capture


@pytest.mark.anyio
async def test_low_confidence_downgrades_to_pending(db_path):
    """confidence_note='Low - uncertain' + demo_mode=True must yield PENDING."""
    captured, capture_fn = _make_capture()

    with (
        patch("config.settings.SQLITE_PATH", db_path),
        patch(
            "services.provider_service.call",
            new_callable=AsyncMock,
            return_value=_moderation_response("Low - uncertain"),
        ),
        patch(
            "services.retrieval_service.retrieve_split",
            return_value=MOCK_RETRIEVAL_CHUNKS,
        ),
        patch(
            "repositories.moderation_repo.create",
            new=AsyncMock(side_effect=capture_fn),
        ),
        patch("services.audit_service.log_interaction", new_callable=AsyncMock),
        patch(
            "repositories.settings_repo.get_demo_mode",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        from services import moderation_service

        result = await moderation_service.analyze(
            "borderline message", EventSource.DASHBOARD
        )

    assert captured["status"] == ModerationStatus.PENDING
    assert result.status == ModerationStatus.PENDING


@pytest.mark.anyio
async def test_moderate_confidence_still_auto_actions(db_path):
    """confidence_note='Moderate - somewhat clear' + demo_mode=True must
    continue to AUTO_ACTIONED — only Low downgrades."""
    captured, capture_fn = _make_capture()

    with (
        patch("config.settings.SQLITE_PATH", db_path),
        patch(
            "services.provider_service.call",
            new_callable=AsyncMock,
            return_value=_moderation_response("Moderate - somewhat clear"),
        ),
        patch(
            "services.retrieval_service.retrieve_split",
            return_value=MOCK_RETRIEVAL_CHUNKS,
        ),
        patch(
            "repositories.moderation_repo.create",
            new=AsyncMock(side_effect=capture_fn),
        ),
        patch("services.audit_service.log_interaction", new_callable=AsyncMock),
        patch(
            "repositories.settings_repo.get_demo_mode",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        from services import moderation_service

        result = await moderation_service.analyze(
            "clearly harassing message", EventSource.DASHBOARD
        )

    assert captured["status"] == ModerationStatus.AUTO_ACTIONED
    assert result.status == ModerationStatus.AUTO_ACTIONED
