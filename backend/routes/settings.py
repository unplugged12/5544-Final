"""Settings endpoints — demo-mode toggle, chat flag, and generic settings CRUD."""

from fastapi import APIRouter

from models.schemas import (
    WRITEABLE_SETTINGS_KEYS,
    ChatEnabledRequest,
    ChatEnabledResponse,
    DemoModeRequest,
    DemoModeResponse,
    SettingsBatchUpdate,
    SettingsPayload,
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


# ---------------------------------------------------------------------------
# Generic settings CRUD (allow-listed keys only)
# ---------------------------------------------------------------------------


@router.get("", response_model=SettingsPayload)
async def get_all_settings() -> SettingsPayload:
    """Return every app_setting value, filtered to the writeable allow-list.

    Secrets (API keys, Discord tokens, HMAC secrets) are never stored in
    app_settings and therefore never appear here — they remain env-only.
    """
    all_rows = await settings_repo.get_all()
    filtered = {k: v for k, v in all_rows.items() if k in WRITEABLE_SETTINGS_KEYS}
    # Ensure every allow-listed key appears even if the row is missing, so
    # the portal can render a full form without defensive null checks.
    for key in WRITEABLE_SETTINGS_KEYS:
        filtered.setdefault(key, "")
    return SettingsPayload(settings=filtered)


@router.post("", response_model=SettingsPayload)
async def update_settings(body: SettingsBatchUpdate) -> SettingsPayload:
    """Upsert one or more app_settings rows. 422 on unknown keys."""
    for key, value in body.updates.items():
        await settings_repo.set(key, value)
    return await get_all_settings()
