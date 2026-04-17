"""Mod-draft service — draft a moderator response for a given situation."""

import logging

from models.enums import TaskType
from models.schemas import TaskResponse
from prompts.mod_draft_prompt import get_system_prompt
from services import audit_service, provider_service, retrieval_service
from services.utils import build_citations_and_rule, extract_confidence

logger = logging.getLogger(__name__)


async def draft(situation: str) -> TaskResponse:
    """Draft a moderator response for *situation*."""
    # 1. Retrieve rules + mod notes
    chunks = retrieval_service.retrieve(
        query=situation,
        source_types=["rule", "mod_note"],
    )

    # 2. Call LLM
    result = await provider_service.call(
        "generate_mod_draft",
        situation=situation,
        context_chunks=chunks,
        system_prompt=get_system_prompt(),
    )

    body, confidence_note = extract_confidence(result.text)

    citations, matched_rule, raw_source_ids = build_citations_and_rule(chunks)

    await audit_service.log_interaction(
        task_type=TaskType.MOD_DRAFT.value,
        input_text=situation,
        output_text=body,
        citations=[ci.model_dump() for ci in citations],
        provider_used=result.provider_name,
    )

    return TaskResponse(
        task_type=TaskType.MOD_DRAFT,
        output_text=body,
        citations=citations,
        confidence_note=confidence_note,
        matched_rule=matched_rule,
        raw_source_ids=raw_source_ids,
    )
