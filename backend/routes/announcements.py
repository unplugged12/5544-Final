"""Announcement summarization endpoint."""

from fastapi import APIRouter

from models.schemas import SummarizeRequest, TaskResponse
from services import summary_service

router = APIRouter()


@router.post("/summarize", response_model=TaskResponse)
async def summarize_announcement(body: SummarizeRequest) -> TaskResponse:
    return await summary_service.summarize(body.text)
