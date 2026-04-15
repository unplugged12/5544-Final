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
 11. Emit structured JSON log (PR 7: observability).
 12. Every 50th turn, run drift watcher (PR 7: anomaly detection).
 13. Return ChatResponse.
"""

import hashlib
import hmac
import json
import logging
import time

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

# ---------------------------------------------------------------------------
# PR 7: turn counter for drift watcher gate.
# Using a module-level counter is intentional at class-project scale — it avoids
# background task complexity (APScheduler, asyncio tasks) while providing a
# reasonable sampling rate. Every 50th turn triggers a 1h lookback query,
# so at 100 req/min the DB query runs at most ~2×/min. Thread-safety is not
# a concern because asyncio is single-threaded per event loop.
# ---------------------------------------------------------------------------
_TURN_COUNTER = 0


def _make_session_id(guild_id: str, channel_id: str, user_id: str) -> str:
    """Return a 16-char hex session identifier for a (guild, channel, user) triple.

    sha256(f"{guild_id}|{channel_id}|{user_id}".encode()).hexdigest()[:16]
    Matches the shape used in the PR 1 echo route.
    """
    raw = f"{guild_id}|{channel_id}|{user_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _hmac_user_id(user_id: str, secret: str) -> str:
    """Return a 16-char HMAC-SHA256 hex digest of user_id.

    guild_id and channel_id are not user-identifying snowflakes (they identify
    the server/channel, not the person), so they are logged as plaintext.
    user_id directly identifies the person and must be HMAC'd before logging.
    The 16-char truncation is sufficient for correlation while bounding entropy
    leakage.
    """
    return hmac.new(
        secret.encode(),
        user_id.encode(),
        "sha256",
    ).hexdigest()[:16]


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
        ChatResponse with reply_text, session_id, refusal flag, provider_used,
        and injection_marker_seen (PR 7 — for auto-timeout in the bot rate limiter).
    """
    global _TURN_COUNTER

    from config import settings  # lazy import — avoids circular imports at module load

    # PR 7: start wall-clock timer for latency_ms
    _start = time.monotonic()

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
    risky_output_marker_seen = contains_risky_output_markers(response.text)
    classify_only_invoked = False

    if risky_output_marker_seen:
        classify_only_invoked = True
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
    # 11. PR 7: Structured per-turn JSON log (observability).
    #
    # Privacy notes:
    #   - user_id_hash: HMAC-SHA256 of user_id, NOT plaintext. Only the
    #     server-side secret (CHAT_LOG_HMAC_SECRET) can link hashes to users.
    #   - guild_id / channel_id are NOT logged as PII — they identify a
    #     community/channel, not a person, so plaintext snowflakes are fine.
    #   - Message content is NEVER logged — only lengths. This prevents log
    #     sinks from becoming a secondary store of user messages.
    # ------------------------------------------------------------------
    latency_ms = int((time.monotonic() - _start) * 1000)

    # Extract token counts from provider response usage dict (0 if unavailable).
    input_tokens: int = response.usage.get("input_tokens") or response.usage.get("prompt_tokens") or 0
    output_tokens: int = response.usage.get("output_tokens") or response.usage.get("completion_tokens") or 0

    log_record = {
        "event": "chat_turn",
        "session_id": session_id,
        "user_id_hash": _hmac_user_id(user_id, settings.CHAT_LOG_HMAC_SECRET),
        "guild_id": guild_id,
        "channel_id": channel_id,
        "input_chars": len(safe_content),
        "output_chars": len(final_text),
        "provider": response.provider_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "refusal": refusal,
        "injection_marker_seen": injection_marker_seen,
        "risky_output_marker_seen": risky_output_marker_seen,
        "classify_only_invoked": classify_only_invoked,
        "latency_ms": latency_ms,
    }
    logger.info(json.dumps(log_record))

    # ------------------------------------------------------------------
    # 12. PR 7: Drift watcher — sample every 50th turn to avoid a DB
    # query on every request. See drift_watcher.py for thresholds.
    # ------------------------------------------------------------------
    _TURN_COUNTER += 1
    if _TURN_COUNTER % 50 == 0:
        from services import drift_watcher  # local import avoids circular at load
        await drift_watcher.check_and_warn()

    # ------------------------------------------------------------------
    # 13. Return
    # ------------------------------------------------------------------
    return ChatResponse(
        reply_text=final_text,
        session_id=session_id,
        refusal=refusal,
        provider_used=response.provider_name,
        injection_marker_seen=injection_marker_seen,
    )
