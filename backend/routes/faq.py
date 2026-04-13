"""FAQ endpoint — retrieval-augmented Q&A."""

from fastapi import APIRouter

from models.schemas import FAQRequest, TaskResponse
from services import faq_service

router = APIRouter()


@router.post("/ask", response_model=TaskResponse)
async def ask_faq(body: FAQRequest) -> TaskResponse:
    return await faq_service.ask(body.question)
