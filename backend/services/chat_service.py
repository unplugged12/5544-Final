"""Chat service — orchestrates the full conversational reply pipeline.

Flow per handle() call:
  1. Compute deterministic session_id from (guild_id, channel_id, user_id).
  2. Sanitize user input via chat_guard.sanitize_input.
  3. Compute injection-marker telemetry signal (against original content).
  4. Load session history from chat_repo (chronological, oldest→newest).
  5. Assemble provider messages: history turns + current user turn wrapped in
     untrusted-data delimiters.
  6. Call provider via provider_service.call("generate_chat_reply", ...).
  7. Gated output moderation: if risky markers present, run classify_only;
     replace reply with canned in-character refusal if severity high/critical.
  8. Scrub output via chat_guard.scrub_output.
  9. Persist user turn and assistant turn to chat_repo.
 10. Audit via audit_service.log_interaction.
 11. Return ChatResponse.
"""

import hashlib
import logging

from models.enums import Severity, TaskType
from models.schemas import ChatResponse
from repositories import chat_repo
from services import audit_service, moderation_service, provider_service
from services.chat_guard import (
    contains_prompt_injection_markers,
    contains_risky_output_markers,
    sanitize_input,
    scrub_output,
)
from prompts.chat_prompt import get_system_prompt

logger = logging.getLogger(__name__)

# Canned in-character refusal phrase — literal string asserted by PR 6 adversarial suite.
_CANNED_REFUSAL = "lol nah, not doing that. wanna ask about events instead?"

# Severity values that trigger a reply replacement
_BLOCK_SEVERITIES: frozenset[str] = frozenset(
    [Severity.HIGH.value, Severity.CRITICAL.value]
)


def _make_session_id(guild_id: str, channel_id: str, user_id: str) -> str:
    """Return a 16-char hex session identifier for a (guild, channel, user) triple.

    sha256(f"{guild_id}|{channel_id}|{user_id}".encode()).hexdigest()[:16]
    Matches the shape used in the PR 1 echo route.
    """
    raw = f"{guild_id}|{channel_id}|{user_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def handle(
    *,
    user_id: str,
    channel_id: str,
    guild_id: str,
    content: str,
) -> ChatResponse:
    """Orchestrate a full conversational reply.

    Args:
        user_id:    Discord user snowflake (string).
        channel_id: Discord channel snowflake (string).
        guild_id:   Discord guild snowflake (string).
        content:    Raw user message text (already validated ≤1500 chars by schema).

    Returns:
        ChatResponse with reply_text, session_id, refusal flag, and provider_used.
    """
    from config import settings  # lazy import — avoids circular imports at module load

    # ------------------------------------------------------------------
    # 1. Compute session_id
    # ------------------------------------------------------------------
    session_id = _make_session_id(guild_id, channel_id, user_id)

    # ------------------------------------------------------------------
    # 2. Sanitize input + 3. Injection marker telemetry
    # ------------------------------------------------------------------
    safe_content = sanitize_input(content)
    injection_marker_seen = contains_prompt_injection_markers(content)  # raw content

    # ------------------------------------------------------------------
    # 4. Load history (chronological: oldest→newest)
    # ------------------------------------------------------------------
    history_turns = await chat_repo.load_session(
        session_id, max_turns=settings.CHAT_HISTORY_MAX_TURNS
    )

    # ------------------------------------------------------------------
    # 5. Assemble messages for the provider
    #
    # Historical turns are NOT re-wrapped — they're already in our trust
    # boundary (were sanitized when first received).
    # The current user message is wrapped in untrusted-data delimiters
    # that the system prompt explicitly identifies as untrusted.
    # ------------------------------------------------------------------
    messages: list[dict] = []
    for turn in history_turns:
        messages.append({"role": turn["role"], "content": turn["content"]})

    wrapped_user_msg = (
        f"<<<USER_MESSAGE from={user_id} trust=untrusted>>>\n"
        f"{safe_content}\n"
        f"<<<END_USER_MESSAGE>>>"
    )
    messages.append({"role": "user", "content": wrapped_user_msg})

    # ------------------------------------------------------------------
    # 6. Call provider
    # ------------------------------------------------------------------
    response = await provider_service.call(
        "generate_chat_reply",
        messages=messages,
        system_prompt=get_system_prompt(),
        max_tokens=settings.CHAT_MODEL_MAX_TOKENS,
    )

    # ------------------------------------------------------------------
    # 7. Gated output moderation
    # ------------------------------------------------------------------
    refusal = False
    if contains_risky_output_markers(response.text):
        moderation_result = await moderation_service.classify_only(response.text)
        if moderation_result.severity.value in _BLOCK_SEVERITIES:
            response_text = _CANNED_REFUSAL
            refusal = True
            logger.info(
                "Output moderation blocked reply for session %s (severity=%s)",
                session_id,
                moderation_result.severity.value,
            )
        else:
            response_text = response.text
    else:
        response_text = response.text

    # ------------------------------------------------------------------
    # 8. Scrub output
    # ------------------------------------------------------------------
    final_text = scrub_output(response_text)

    # ------------------------------------------------------------------
    # 9. Persist user turn then assistant turn
    #    (scrubbed text is what the user sees — persist the scrubbed version)
    # ------------------------------------------------------------------
    await chat_repo.insert_turn(
        session_id=session_id,
        guild_id=guild_id,
        channel_id=channel_id,
        user_id=user_id,
        role="user",
        content=safe_content,
        ttl_minutes=settings.CHAT_HISTORY_TTL_MINUTES,
    )
    await chat_repo.insert_turn(
        session_id=session_id,
        guild_id=guild_id,
        channel_id=channel_id,
        user_id=user_id,
        role="assistant",
        content=final_text,
        ttl_minutes=settings.CHAT_HISTORY_TTL_MINUTES,
    )

    # ------------------------------------------------------------------
    # 10. Audit
    # ------------------------------------------------------------------
    await audit_service.log_interaction(
        task_type=TaskType.CHAT.value,
        input_text=safe_content,
        output_text=final_text,
        citations=[],
        provider_used=response.provider_name,
    )

    # ------------------------------------------------------------------
    # 11. Return
    # ------------------------------------------------------------------
    logger.info(
        "chat_service.handle: session=%s refusal=%s injection_marker=%s provider=%s",
        session_id,
        refusal,
        injection_marker_seen,
        response.provider_name,
    )

    return ChatResponse(
        reply_text=final_text,
        session_id=session_id,
        refusal=refusal,
        provider_used=response.provider_name,
    )
