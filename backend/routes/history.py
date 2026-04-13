"""History endpoint — paginated list of moderation events."""

from fastapi import APIRouter, Query

from models.schemas import HistoryResponse
from repositories import moderation_repo

router = APIRouter()


@router.get("", response_model=HistoryResponse)
async def list_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
) -> HistoryResponse:
    events, total = await moderation_repo.list_events(
        limit=limit, offset=offset, status=status
    )
    return HistoryResponse(events=events, total=total)
