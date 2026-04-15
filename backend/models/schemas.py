"""Pydantic models for request/response payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from models.enums import (
    EventSource,
    ModerationStatus,
    Severity,
    SourceType,
    SuggestedAction,
    TaskType,
    ViolationType,
)


# ---------------------------------------------------------------------------
# Knowledge / source items
# ---------------------------------------------------------------------------

class KnowledgeItem(BaseModel):
    source_id: str
    source_type: SourceType
    title: str
    content: str
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    citation_label: str
    created_at: str


class SourcesResponse(BaseModel):
    sources: list[KnowledgeItem]
    total: int


# ---------------------------------------------------------------------------
# Citation helper
# ---------------------------------------------------------------------------

class Citation(BaseModel):
    source_id: str
    citation_label: str
    snippet: str


# ---------------------------------------------------------------------------
# Task responses (FAQ, summary, mod_draft)
# ---------------------------------------------------------------------------

class TaskResponse(BaseModel):
    task_type: TaskType
    output_text: str
    citations: list[Citation] = Field(default_factory=list)
    confidence_note: str | None = None
    matched_rule: str | None = None
    severity: Severity | None = None
    suggested_action: SuggestedAction | None = None
    raw_source_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Moderation events
# ---------------------------------------------------------------------------

class ModerationEventResponse(BaseModel):
    event_id: str
    message_content: str
    violation_type: ViolationType
    matched_rule: str | None = None
    explanation: str
    severity: Severity
    suggested_action: SuggestedAction
    status: ModerationStatus
    source: EventSource
    created_at: str
    resolved_at: str | None = None
    resolved_by: str | None = None


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class FAQRequest(BaseModel):
    question: str


class SummarizeRequest(BaseModel):
    text: str


class ModDraftRequest(BaseModel):
    situation: str


class AnalyzeRequest(BaseModel):
    message_content: str
    source: EventSource = EventSource.DASHBOARD


class DemoModeRequest(BaseModel):
    enabled: bool


# ---------------------------------------------------------------------------
# Simple responses
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    demo_mode: bool = True
    provider: str = "openai"
    knowledge_count: int = 0


class DemoModeResponse(BaseModel):
    demo_mode: bool


class HistoryResponse(BaseModel):
    events: list[ModerationEventResponse]
    total: int


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    user_id: str
    channel_id: str
    guild_id: str
    content: str

    @field_validator("content")
    @classmethod
    def content_within_max_chars(cls, v: str) -> str:
        # Lazy import avoids potential circular dependency at module load time.
        from config import settings  # noqa: PLC0415

        limit = settings.CHAT_INPUT_MAX_CHARS
        if len(v) > limit:
            raise ValueError(
                f"content exceeds CHAT_INPUT_MAX_CHARS limit of {limit} characters"
            )
        return v


class ChatResponse(BaseModel):
    reply_text: str
    session_id: str
    refusal: bool
    provider_used: str


class ChatEnabledRequest(BaseModel):
    enabled: bool


class ChatEnabledResponse(BaseModel):
    chat_enabled: bool
