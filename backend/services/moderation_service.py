"""Moderation service — analyse messages, create events, handle approvals."""

import json
import logging
import uuid

from models.enums import (
    EventSource,
    ModerationStatus,
    Severity,
    SuggestedAction,
    TaskType,
    ViolationType,
)
from models.schemas import ModerationEventResponse
from prompts.moderation_prompt import get_system_prompt
from repositories import moderation_repo, settings_repo
from services import audit_service, provider_service, retrieval_service

logger = logging.getLogger(__name__)


def _safe_parse_json(text: str) -> dict:
    """Strip markdown fences and parse JSON.  Returns a dict or raises."""
    cleaned = (
        text.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    return json.loads(cleaned)


async def analyze(
    message_content: str,
    source: EventSource,
) -> ModerationEventResponse:
    """Run moderation analysis and persist the event."""

    # 1. Retrieve rule + mod_note chunks
    chunks = retrieval_service.retrieve(
        query=message_content,
        source_types=["rule", "mod_note"],
    )

    # 2. Call LLM
    result = await provider_service.call(
        "generate_moderation_analysis",
        message_content=message_content,
        rule_chunks=chunks,
        system_prompt=get_system_prompt(),
    )

    # 3. Parse JSON response
    try:
        parsed = _safe_parse_json(result.text)
        violation_type = ViolationType(parsed.get("violation_type", "no_violation"))
        matched_rule = parsed.get("matched_rule")
        explanation = parsed.get("explanation", "")
        severity = Severity(parsed.get("severity", "low"))
        suggested_action = SuggestedAction(
            parsed.get("suggested_action", "no_action")
        )
        confidence_note = parsed.get("confidence_note", "")
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.warning("Failed to parse moderation JSON: %s", exc)
        violation_type = ViolationType.NO_VIOLATION
        matched_rule = None
        explanation = "Analysis could not be parsed"
        severity = Severity.LOW
        suggested_action = SuggestedAction.NO_ACTION
        confidence_note = "Low - parse failure"

    # 4. Determine status based on demo mode
    demo_mode = await settings_repo.get_demo_mode()

    auto_action_triggers = {
        SuggestedAction.REMOVE_MESSAGE,
        SuggestedAction.TIMEOUT_RECOMMENDATION,
        SuggestedAction.ESCALATE,
    }

    if demo_mode and suggested_action in auto_action_triggers:
        status = ModerationStatus.AUTO_ACTIONED
    else:
        status = ModerationStatus.PENDING

    # 5. Persist the event
    event_id = uuid.uuid4().hex
    event = await moderation_repo.create(
        event_id=event_id,
        message_content=message_content,
        violation_type=violation_type,
        matched_rule=matched_rule,
        explanation=explanation,
        severity=severity,
        suggested_action=suggested_action,
        status=status,
        source=source,
    )

    # 6. Audit
    await audit_service.log_interaction(
        task_type=TaskType.MODERATION.value,
        input_text=message_content,
        output_text=explanation,
        citations=[],
        provider_used=result.provider_name,
    )

    return event


async def approve(event_id: str) -> ModerationEventResponse | None:
    """Set event status to approved."""
    return await moderation_repo.update_status(
        event_id, ModerationStatus.APPROVED, resolved_by="dashboard"
    )


async def reject(event_id: str) -> ModerationEventResponse | None:
    """Set event status to rejected."""
    return await moderation_repo.update_status(
        event_id, ModerationStatus.REJECTED, resolved_by="dashboard"
    )
