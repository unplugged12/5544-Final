"""Knowledge-source browsing endpoints."""

from fastapi import APIRouter, Query

from models.enums import SourceType
from models.schemas import SourcesResponse
from repositories import knowledge_repo

router = APIRouter()


@router.get("/sources", response_model=SourcesResponse)
async def list_sources(
    source_type: SourceType | None = Query(default=None),
) -> SourcesResponse:
    items = await knowledge_repo.get_all(source_type=source_type)
    return SourcesResponse(sources=items, total=len(items))
