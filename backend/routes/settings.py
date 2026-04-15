"""Settings endpoints — demo-mode toggle and chat-enabled flag."""

from fastapi import APIRouter

from models.schemas import (
    ChatEnabledRequest,
    ChatEnabledResponse,
    DemoModeRequest,
    DemoModeResponse,
)
from repositories import settings_repo

router = APIRouter()


@router.get("/demo-mode", response_model=DemoModeResponse)
async def get_demo_mode() -> DemoModeResponse:
    enabled = await settings_repo.get_demo_mode()
    return DemoModeResponse(demo_mode=enabled)


@router.post("/demo-mode", response_model=DemoModeResponse)
async def set_demo_mode(body: DemoModeRequest) -> DemoModeResponse:
    await settings_repo.set_demo_mode(body.enabled)
    return DemoModeResponse(demo_mode=body.enabled)


@router.get("/chat-enabled", response_model=ChatEnabledResponse)
async def get_chat_enabled_setting() -> ChatEnabledResponse:
    """Return the current chat-enabled flag (defaults to False if unset)."""
    val = await settings_repo.get("chat_enabled")
    enabled = val == "true" if val is not None else False
    return ChatEnabledResponse(chat_enabled=enabled)


@router.post("/chat-enabled", response_model=ChatEnabledResponse)
async def set_chat_enabled_setting(body: ChatEnabledRequest) -> ChatEnabledResponse:
    """Persist the chat-enabled flag via the generic settings_repo."""
    await settings_repo.set("chat_enabled", "true" if body.enabled else "false")
    return ChatEnabledResponse(chat_enabled=body.enabled)
