"""Drift watcher — periodic anomaly detection for chat quality signals.

check_and_warn() is called from chat_service.handle every 50th turn (counter-
gated). This avoids a DB query on every request while still providing roughly
real-time alerting at moderate load. At 100 req/min the query runs at most
~2×/min — acceptable for a class-project SQLite deployment.

Thresholds (from spec):
  - refusal_rate > 0.20 (20%) over the last 1h window → WARNING
  - avg_output_chars < 20 over the last 1h window → WARNING

These thresholds are deliberately conservative: a 20% refusal rate in 1h
indicates either a coordinated injection campaign or a broken output-moderation
pipeline. An avg output of < 20 chars suggests the provider is truncating or
returning empty/error strings.

Design note: no APScheduler, no background task. The 50-turn gate in
chat_service is intentionally simple — it keeps this module side-effect-free
until called, which makes it easy to test with a mocked DB.
"""

import logging

import aiosqlite

from config import settings

logger = logging.getLogger(__name__)

# Minimum number of turns in the 1h window required to evaluate thresholds.
# Below this floor, we have insufficient data and skip the check to avoid
# false positives from a cold start (e.g., first 5 turns after deploy).
_MIN_SAMPLE_SIZE = 5

# Anomaly thresholds
_REFUSAL_RATE_THRESHOLD = 0.20   # 20% refusal rate
_AVG_OUTPUT_CHARS_THRESHOLD = 20  # minimum expected average output length


async def check_and_warn() -> None:
    """Query the last 1h of chat audit data and log warnings on anomalies.

    Reads from interaction_history (task_type='chat') because chat_turns is
    hot-session state only (TTL'd at 15 min) and doesn't carry refusal flags.
    interaction_history is the permanent audit trail (PR 1).

    Note: interaction_history does NOT store refusal flags or output_chars
    natively — we approximate refusal from output_text equality with the
    canned refusal phrase, and output_chars from len(output_text). This is
    a best-effort heuristic; a future PR with a log shipper integration can
    replace it with the structured log fields.
    """
    try:
        async with aiosqlite.connect(settings.SQLITE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT output_text
                FROM interaction_history
                WHERE task_type = 'chat'
                  AND created_at >= datetime('now', '-1 hour')
                """,
            )
            rows = await cursor.fetchall()
    except Exception:
        logger.exception("drift_watcher: DB query failed — skipping anomaly check")
        return

    if len(rows) < _MIN_SAMPLE_SIZE:
        # Not enough data in the 1h window — skip to avoid cold-start false positives.
        return

    from services.chat_service import _CANNED_REFUSAL  # avoids circular import at module level

    total = len(rows)
    refusals = sum(1 for r in rows if r["output_text"] == _CANNED_REFUSAL)
    output_chars = [len(r["output_text"]) for r in rows]
    avg_output = sum(output_chars) / total

    refusal_rate = refusals / total

    if refusal_rate > _REFUSAL_RATE_THRESHOLD:
        logger.warning(
            "chat_drift: refusal_rate=%.2f over 1h window (%d/%d turns)",
            refusal_rate,
            refusals,
            total,
        )

    if avg_output < _AVG_OUTPUT_CHARS_THRESHOLD:
        logger.warning(
            "chat_drift: avg_output_chars=%.1f over 1h window (%d turns)",
            avg_output,
            total,
        )
