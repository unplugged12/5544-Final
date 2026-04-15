"""Chat endpoint — delegates to chat_service.handle.

POST /api/chat → ChatResponse.

The route is a thin HTTP shim: it validates the request body (via the
ChatRequest Pydantic schema) and delegates all business logic — history
loading, provider call, output moderation, scrubbing, persistence, and
audit — to chat_service.handle.
"""

from fastapi import APIRouter

from models.schemas import ChatRequest, ChatResponse
from services import chat_service

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def post_chat(body: ChatRequest) -> ChatResponse:
    """Dispatch a chat message through the full service pipeline."""
    return await chat_service.handle(
        user_id=body.user_id,
        channel_id=body.channel_id,
        guild_id=body.guild_id,
        content=body.content,
    )
