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
import re
import time

from models.enums import Severity, TaskType
from models.schemas import ChatResponse
from repositories import chat_repo
from services import audit_service, moderation_service, provider_service, retrieval_service
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

# Source types eligible for chat retrieval. mod_note is intentionally excluded:
# it may contain PII or draft discipline reasoning that should never surface in
# a user-facing chat reply.
_CHAT_RETRIEVAL_SOURCE_TYPES: list[str] = ["rule", "faq", "announcement"]

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

# ---------------------------------------------------------------------------
# PR 7 fix (P2): HMAC secret sentinel guard.
# If CHAT_LOG_HMAC_SECRET is unconfigured (empty or still the sentinel), the
# sentinel key is public in the repo — anyone who knows it can compute the same
# hashes and reverse the pseudonymization guarantee. Instead: log user_id_hash
# as None and emit one error per process lifetime so operators notice the
# misconfiguration without crashing the chat flow.
# ---------------------------------------------------------------------------
_HMAC_SECRET_SENTINEL = "REPLACE_ME_WITH_SECRET"
_hmac_warned = False


def reset_hmac_warning_state() -> None:
    """Reset the per-process HMAC warning guard. For tests only."""
    global _hmac_warned
    _hmac_warned = False


def _sanitize_reference_chunk(text: str, max_chars: int) -> str:
    """Neutralize trust-boundary delimiters and cap length in a KB chunk.

    Applied at query time before a chunk is injected into the LLM prompt.
    Mirrors the guillemet substitution in chat_guard.sanitize_input so a
    poisoned KB row containing ``<<<END_REFERENCE_CONTEXT>>>`` (or any other
    triple-bracket sequence) cannot terminate the reference block early and
    smuggle instructions into the model's trust-trusted context.

    Length cap bounds the per-chunk token cost and limits the blast radius
    of a single poisoned row.
    """
    text = text.replace("<<<", "\u2039\u2039\u2039")  # ‹‹‹
    text = text.replace(">>>", "\u203A\u203A\u203A")  # ›››
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return text


def _build_reference_block(chunks: list[dict], max_chars: int) -> str:
    """Assemble the <<<REFERENCE_CONTEXT>>> prompt block from retrieved chunks.

    Each chunk is emitted with its citation_label and sanitized content so the
    model has the label to cite by name, not by source_id. citation_label and
    title are also sanitized — they come from KB metadata and must not be
    trusted as commands.
    """
    if not chunks:
        return ""

    lines: list[str] = ["<<<REFERENCE_CONTEXT trust=trusted>>>"]
    for chunk in chunks:
        label = _sanitize_reference_chunk(
            chunk.get("citation_label") or chunk.get("source_id", ""), max_chars=120
        )
        content = _sanitize_reference_chunk(chunk.get("content", ""), max_chars=max_chars)
        lines.append(f"[{label}]")
        lines.append(content)
        lines.append("")
    lines.append("<<<END_REFERENCE_CONTEXT>>>")
    return "\n".join(lines)


def _label_matches(label: str, reply_lower: str) -> bool:
    """Return True if *label* appears in *reply_lower* on word boundaries.

    Plain substring matching causes false positives when labels share a
    numeric prefix — "Rule 1" would match inside "Rule 10" and every other
    two-digit rule. Use regex word boundaries so "Rule 1" only matches a
    standalone "Rule 1" token (the "0" following a "1" prevents a word
    boundary, so "Rule 10" never matches "Rule 1").

    Labels are user-editable KB metadata and may contain regex metacharacters
    (parentheses, dots, etc.), so the label is escaped before compilation.
    """
    if not label:
        return False
    pattern = r"\b" + re.escape(label) + r"\b"
    return re.search(pattern, reply_lower) is not None


def _resolve_citations(reply_text: str, chunks: list[dict]) -> list[str]:
    """Return source_ids whose citation_label or title the reply actually references.

    Never trust the model to produce source_ids directly — it will hallucinate
    plausible-looking strings. Instead, check whether any retrieved chunk's
    citation_label (or title as a fallback) appears in the reply text on
    word boundaries, and return only those source_ids. A hallucinated label
    the model invented, or a substring-only prefix collision ("Rule 1" inside
    "Rule 10"), is silently dropped.
    """
    if not chunks:
        return []
    lower_reply = reply_text.lower()
    cited: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        source_id = chunk.get("source_id", "")
        if not source_id or source_id in seen:
            continue
        label = (chunk.get("citation_label") or "").lower().strip()
        title = (chunk.get("title") or "").lower().strip()
        if _label_matches(label, lower_reply) or _label_matches(title, lower_reply):
            cited.append(source_id)
            seen.add(source_id)
    return cited


def _retrieve_chat_context(query: str) -> list[dict]:
    """Retrieve chat-appropriate KB chunks for *query*.

    Scoped to rule/faq/announcement types (mod_note intentionally excluded).
    Chunks above the distance threshold are dropped so unrelated questions
    return [] and the model falls back to "not sure" rather than hallucinating
    a grounded answer from noise.

    Returns [] on any retrieval error — chat degrades to ungrounded mode
    gracefully rather than failing the whole request.
    """
    from config import settings  # lazy import
    try:
        chunks = retrieval_service.retrieve(
            query,
            source_types=_CHAT_RETRIEVAL_SOURCE_TYPES,
            top_k=settings.CHAT_TOP_K,
        )
    except Exception:
        logger.exception("Chat retrieval failed — falling back to ungrounded reply")
        return []

    threshold = settings.CHAT_RETRIEVAL_SCORE_THRESHOLD
    return [c for c in chunks if c.get("distance", 1.0) <= threshold]


def _make_session_id(guild_id: str, channel_id: str, user_id: str) -> str:
    """Return a 16-char hex session identifier for a (guild, channel, user) triple.

    sha256(f"{guild_id}|{channel_id}|{user_id}".encode()).hexdigest()[:16]
    Matches the shape used in the PR 1 echo route.
    """
    raw = f"{guild_id}|{channel_id}|{user_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _compute_user_id_hash(user_id: str) -> str | None:
    """Return a 16-char HMAC-SHA256 hex digest of user_id, or None if unconfigured.

    guild_id and channel_id are not user-identifying snowflakes (they identify
    the server/channel, not the person), so they are logged as plaintext.
    user_id directly identifies the person and must be HMAC'd before logging.
    The 16-char truncation is sufficient for correlation while bounding entropy
    leakage.

    If CHAT_LOG_HMAC_SECRET is unconfigured (empty string or sentinel), returns
    None and emits a one-per-process-lifetime error log. This prevents the
    sentinel key (public in the repo) from being used to produce deterministic
    hashes that are reversible by anyone who knows the sentinel value.
    Chat flow continues normally — only the log field is degraded to None.
    """
    global _hmac_warned
    from config import settings as _settings  # local import avoids circular at module load
    secret = _settings.CHAT_LOG_HMAC_SECRET or ""
    if not secret or secret == _HMAC_SECRET_SENTINEL:
        if not _hmac_warned:
            logger.error(
                "CHAT_LOG_HMAC_SECRET is unconfigured (empty or sentinel). "
                "Chat turn logs will record user_id_hash=None. "
                "Pseudonymization is disabled."
            )
            _hmac_warned = True
        return None
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
    # 4b. Retrieve KB context (Chroma). Scoped to rule/faq/announcement;
    # mod_note excluded so draft discipline reasoning and PII in mod notes
    # never surfaces in user-facing chat replies. Chunks are sanitized +
    # length-capped before injection so a poisoned KB row cannot use
    # triple-bracket delimiters to escape the reference block.
    # ------------------------------------------------------------------
    retrieved_chunks = _retrieve_chat_context(safe_content)
    reference_block = _build_reference_block(
        retrieved_chunks, max_chars=settings.CHAT_REFERENCE_CHUNK_MAX_CHARS
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
    # 6. Call provider. Reference context is appended to the system prompt
    # (not the user turn) so the model treats it as trusted operator-provided
    # data parallel to the persona/identity lock, while the user turn stays
    # in the untrusted-data envelope.
    # ------------------------------------------------------------------
    system_prompt = get_system_prompt()
    if reference_block:
        system_prompt = f"{system_prompt}\n\n{reference_block}"

    response = await provider_service.call(
        "generate_chat_reply",
        messages=messages,
        system_prompt=system_prompt,
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
    # 9b. Resolve citations from retrieved chunks (never trust model output
    # to produce source_ids — it will hallucinate).
    # ------------------------------------------------------------------
    citations = _resolve_citations(final_text, retrieved_chunks)

    # ------------------------------------------------------------------
    # 10. Audit
    # ------------------------------------------------------------------
    await audit_service.log_interaction(
        task_type=TaskType.CHAT.value,
        input_text=safe_content,
        output_text=final_text,
        citations=citations,
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
        "user_id_hash": _compute_user_id_hash(user_id),
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
        "retrieved_chunk_count": len(retrieved_chunks),
        "cited_count": len(citations),
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
        citations=citations,
    )
