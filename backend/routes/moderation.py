"""Moderation endpoints — analyze, approve, reject, and draft."""

from fastapi import APIRouter, HTTPException

from models.schemas import (
    AnalyzeRequest,
    ModDraftRequest,
    ModerationEventResponse,
    TaskResponse,
)
from services import mod_draft_service, moderation_service

router = APIRouter()


@router.post("/draft", response_model=TaskResponse)
async def draft_mod_response(body: ModDraftRequest) -> TaskResponse:
    return await mod_draft_service.draft(body.situation)


@router.post("/analyze", response_model=ModerationEventResponse)
async def analyze_message(body: AnalyzeRequest) -> ModerationEventResponse:
    return await moderation_service.analyze(body.message_content, body.source)


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
