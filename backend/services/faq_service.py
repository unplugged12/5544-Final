"""FAQ service — grounded Q&A over the knowledge base."""

import logging

from models.schemas import TaskResponse
from models.enums import TaskType
from prompts.faq_prompt import get_system_prompt
from services import audit_service, provider_service, retrieval_service
from services.utils import build_citations_and_rule, extract_confidence

logger = logging.getLogger(__name__)


async def ask(question: str) -> TaskResponse:
    """Answer a FAQ question with retrieval-augmented generation."""
    # 1. Retrieve context from rules, FAQs, and announcements
    chunks = retrieval_service.retrieve(
        query=question,
        source_types=["rule", "faq", "announcement"],
    )

    # 2. Call the LLM
    result = await provider_service.call(
        "generate_grounded_answer",
        query=question,
        context_chunks=chunks,
        system_prompt=get_system_prompt(),
    )

    # 3. Parse response
    body, confidence_note = extract_confidence(result.text)

    # 4. Build citations + rule match + source IDs
    citations, matched_rule, raw_source_ids = build_citations_and_rule(chunks)

    # 5. Audit
    await audit_service.log_interaction(
        task_type=TaskType.FAQ.value,
        input_text=question,
        output_text=body,
        citations=[ci.model_dump() for ci in citations],
        provider_used=result.provider_name,
    )

    return TaskResponse(
        task_type=TaskType.FAQ,
        output_text=body,
        citations=citations,
        confidence_note=confidence_note,
        matched_rule=matched_rule,
        raw_source_ids=raw_source_ids,
    )
