"""Settings endpoints — demo-mode toggle."""

from fastapi import APIRouter

from models.schemas import DemoModeRequest, DemoModeResponse
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
