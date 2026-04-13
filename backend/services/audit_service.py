"""Audit service — logs every LLM interaction to the history table."""

import logging
import uuid

from repositories import history_repo

logger = logging.getLogger(__name__)


async def log_interaction(
    *,
    task_type: str,
    input_text: str,
    output_text: str,
    citations: list[dict],
    provider_used: str,
) -> str:
    """Persist an interaction and return the generated interaction_id."""
    interaction_id = uuid.uuid4().hex
    await history_repo.create(
        interaction_id=interaction_id,
        task_type=task_type,
        input_text=input_text,
        output_text=output_text,
        citations=citations,
        provider_used=provider_used,
    )
    logger.info(
        "Logged interaction %s (task=%s, provider=%s)",
        interaction_id,
        task_type,
        provider_used,
    )
    return interaction_id
