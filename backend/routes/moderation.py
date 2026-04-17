"""Moderation endpoints — analyze, approve, reject, draft, undo."""

from fastapi import APIRouter, HTTPException

from models.schemas import (
    AnalyzeRequest,
    ModDraftRequest,
    ModerationEventResponse,
    TaskResponse,
)
from services import discipline_service, mod_draft_service, moderation_service

router = APIRouter()


@router.post("/draft", response_model=TaskResponse)
async def draft_mod_response(body: ModDraftRequest) -> TaskResponse:
    return await mod_draft_service.draft(body.situation)


@router.post("/analyze", response_model=ModerationEventResponse)
async def analyze_message(body: AnalyzeRequest) -> ModerationEventResponse:
    return await moderation_service.analyze(
        body.message_content,
        body.source,
        discord_user_id=body.discord_user_id,
        discord_guild_id=body.discord_guild_id,
    )


@router.post("/approve/{event_id}", response_model=ModerationEventResponse)
async def approve_event(event_id: str) -> ModerationEventResponse:
    event = await moderation_service.approve(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/reject/{event_id}", response_model=ModerationEventResponse)
async def reject_event(event_id: str) -> ModerationEventResponse:
    event = await moderation_service.reject(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/undo/{event_id}")
async def undo_event(event_id: str) -> dict:
    """Revoke the discipline action attached to an event and reset the ledger.

    Returns 404 when the event does not exist, 409 when it has no Discord
    context to undo against (dashboard-sourced analyses, for instance).
    """
    result = await discipline_service.undo_for_event(event_id)
    if not result.get("undone"):
        reason = result.get("reason", "unknown")
        if reason == "event_not_found":
            raise HTTPException(status_code=404, detail="Event not found")
        raise HTTPException(
            status_code=409,
            detail=f"Cannot undo event: {reason}",
        )
    return result
