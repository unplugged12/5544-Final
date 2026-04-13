"""Summary service — summarize announcements or arbitrary text."""

import logging

from models.enums import TaskType
from models.schemas import TaskResponse
from prompts.summary_prompt import get_system_prompt
from services import audit_service, provider_service
from services.utils import extract_confidence

logger = logging.getLogger(__name__)


async def summarize(text: str) -> TaskResponse:
    """Summarize the provided text.  No retrieval needed."""
    result = await provider_service.call(
        "generate_summary",
        text=text,
        system_prompt=get_system_prompt(),
    )

    body, confidence_note = extract_confidence(result.text)

    await audit_service.log_interaction(
        task_type=TaskType.SUMMARY.value,
        input_text=text,
        output_text=body,
        citations=[],
        provider_used=result.provider_name,
    )

    return TaskResponse(
        task_type=TaskType.SUMMARY,
        output_text=body,
        confidence_note=confidence_note,
    )
