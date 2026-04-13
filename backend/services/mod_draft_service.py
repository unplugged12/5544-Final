"""Mod-draft service — draft a moderator response for a given situation."""

import logging

from models.enums import TaskType
from models.schemas import Citation, TaskResponse
from prompts.mod_draft_prompt import get_system_prompt
from services import audit_service, provider_service, retrieval_service
from services.utils import extract_confidence

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

    citations = [
        Citation(
            source_id=c["source_id"],
            citation_label=c["citation_label"],
            snippet=c["content"][:150],
        )
        for c in chunks
    ]

    matched_rule = next(
        (c["citation_label"] for c in chunks if c.get("source_type") == "rule"),
        None,
    )

    raw_source_ids = [c["source_id"] for c in chunks]

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
