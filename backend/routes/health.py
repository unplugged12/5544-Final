"""Health-check endpoint."""

from fastapi import APIRouter

from config import settings
from models.schemas import HealthResponse
from repositories import knowledge_repo, settings_repo

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    demo_mode = await settings_repo.get_demo_mode()
    knowledge_count = await knowledge_repo.count()

    return HealthResponse(
        status="ok",
        demo_mode=demo_mode,
        provider=settings.PRIMARY_PROVIDER,
        knowledge_count=knowledge_count,
    )
