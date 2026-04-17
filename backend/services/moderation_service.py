"""Moderation service — analyse messages, create events, handle approvals."""

import json
import logging
import uuid
from dataclasses import dataclass

from models.enums import (
    EventSource,
    ModerationStatus,
    Severity,
    SuggestedAction,
    TaskType,
    ViolationType,
)
from models.schemas import DisciplineDecisionPayload, ModerationEventResponse
from prompts.moderation_prompt import get_system_prompt
from repositories import moderation_repo, settings_repo
from services import (
    audit_service,
    discipline_service,
    provider_service,
    retrieval_service,
)
from services.utils import parse_json_response

logger = logging.getLogger(__name__)


@dataclass
class ModerationLLMResult:
    """Parsed LLM result from a moderation call — no persistence fields."""

    violation_type: ViolationType
    matched_rule: str | None
    explanation: str
    severity: Severity
    suggested_action: SuggestedAction
    confidence_note: str
    provider_name: str


async def _run_moderation_llm(text: str) -> ModerationLLMResult:
    """Call the LLM for moderation and parse the JSON — NO persistence, NO audit.

    This private helper is the shared core used by both ``analyze`` (which adds
    persistence + audit) and ``classify_only`` (which skips both, for chat
    output moderation where we do not want a dashboard event per message).
    """
    # Retrieve rule + mod_note chunks
    chunks = retrieval_service.retrieve(
        query=text,
        source_types=["rule", "mod_note"],
    )

    # Call LLM
    result = await provider_service.call(
        "generate_moderation_analysis",
        message_content=text,
        rule_chunks=chunks,
        system_prompt=get_system_prompt(),
    )

    # Parse JSON response
    try:
        parsed = parse_json_response(result.text)
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

    return ModerationLLMResult(
        violation_type=violation_type,
        matched_rule=matched_rule,
        explanation=explanation,
        severity=severity,
        suggested_action=suggested_action,
        confidence_note=confidence_note,
        provider_name=result.provider_name,
    )


async def classify_only(text: str) -> ModerationLLMResult:
    """Run moderation LLM + parse — NO persistence, NO audit.

    Used by chat_service for gated output moderation on chat replies.
    Calling this does NOT create a moderation_events row and does NOT write
    to interaction_history, so chat replies do not pollute the dashboard.

    The gate in chat_service (``chat_guard.contains_risky_output_markers``)
    ensures this is called only on the ~10-15% of replies that contain risky
    surface patterns, keeping the second LLM call rate low.
    """
    return await _run_moderation_llm(text)


async def analyze(
    message_content: str,
    source: EventSource,
    *,
    discord_user_id: str | None = None,
    discord_guild_id: str | None = None,
) -> ModerationEventResponse:
    """Run moderation analysis, persist the event, and return the decision.

    Public API is extended (not broken) — callers that don't pass Discord
    context still get a valid ModerationEventResponse, just without a
    discipline_decision attached. Bot callers supply the Discord IDs so
    the progressive-discipline engine can update the per-user ledger.
    """
    # 1-3. LLM call + parse (no persistence)
    llm_result = await _run_moderation_llm(message_content)

    # 4. Determine status based on demo mode
    demo_mode = await settings_repo.get_demo_mode()

    auto_action_triggers = {
        SuggestedAction.REMOVE_MESSAGE,
        SuggestedAction.TIMEOUT_RECOMMENDATION,
        SuggestedAction.ESCALATE,
    }

    if demo_mode and llm_result.suggested_action in auto_action_triggers:
        status = ModerationStatus.AUTO_ACTIONED
    else:
        status = ModerationStatus.PENDING

    # 5. Persist the event
    event_id = uuid.uuid4().hex
    event = await moderation_repo.create(
        event_id=event_id,
        message_content=message_content,
        violation_type=llm_result.violation_type,
        matched_rule=llm_result.matched_rule,
        explanation=llm_result.explanation,
        severity=llm_result.severity,
        suggested_action=llm_result.suggested_action,
        status=status,
        source=source,
        discord_user_id=discord_user_id,
        discord_guild_id=discord_guild_id,
    )

    # 6. Progressive discipline — only fires when the event is auto_actioned
    # *and* we have Discord context to attribute it to. Dashboard-sourced
    # /analyze calls from the Review Queue test box deliberately skip this.
    decision_payload: DisciplineDecisionPayload | None = None
    if (
        status == ModerationStatus.AUTO_ACTIONED
        and discord_user_id
        and discord_guild_id
    ):
        decision = await discipline_service.decide_and_record(
            event_id=event_id,
            guild_id=discord_guild_id,
            user_id=discord_user_id,
            category=llm_result.violation_type.value,
            severity=llm_result.severity,
        )
        await moderation_repo.set_discipline_action(event_id, decision.action.value)
        event = event.model_copy(update={"discipline_action": decision.action})
        decision_payload = DisciplineDecisionPayload(**decision.to_dict())

    event = event.model_copy(update={"discipline_decision": decision_payload})

    # 7. Audit
    await audit_service.log_interaction(
        task_type=TaskType.MODERATION.value,
        input_text=message_content,
        output_text=llm_result.explanation,
        citations=[],
        provider_used=llm_result.provider_name,
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
