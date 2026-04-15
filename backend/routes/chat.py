"""Chat endpoint — PR 1 echo stub (no LLM).

Returns an echo ChatResponse so the route shape and schema can be tested
end-to-end before the LLM provider is wired in PR 2.

session_id is derived deterministically from (guild_id, channel_id, user_id)
using the first 16 hex chars of SHA-256 so callers can correlate turns.
"""

import hashlib

from fastapi import APIRouter

from models.schemas import ChatRequest, ChatResponse

router = APIRouter()


def _make_session_id(guild_id: str, channel_id: str, user_id: str) -> str:
    """Return a 16-char hex session identifier for a (guild, channel, user) triple."""
    raw = f"{guild_id}|{channel_id}|{user_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@router.post("/chat", response_model=ChatResponse)
async def post_chat(body: ChatRequest) -> ChatResponse:
    """Echo stub — reflects content back as reply_text.  No LLM call in PR 1.

    PR 2 will replace the echo with a real provider call through chat_service.
    provider_used is set to 'echo' so callers can distinguish stub responses
    from real ones during integration testing.
    """
    session_id = _make_session_id(body.guild_id, body.channel_id, body.user_id)
    return ChatResponse(
        reply_text=body.content,
        session_id=session_id,
        refusal=False,
        provider_used="echo",
    )
