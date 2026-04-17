"""Repository for user_violations + mod_actions tables.

Progressive-discipline bookkeeping. Each auto-actioned event contributes
one user_violations row (the severity-weighted "point ledger") and one
mod_actions row (the audit trail). Undo by the dashboard revokes both.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import aiosqlite

from config import settings
from models.enums import ModActionType, Severity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# severity → points (design decision, see PAM project doc)
# ---------------------------------------------------------------------------

SEVERITY_POINTS: dict[Severity, int] = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 5,
}


def points_for(severity: Severity) -> int:
    return SEVERITY_POINTS.get(severity, 1)


# ---------------------------------------------------------------------------
# user_violations
# ---------------------------------------------------------------------------


async def add_violation(
    *,
    event_id: str,
    guild_id: str,
    user_id: str,
    category: str,
    severity: Severity,
) -> str:
    """Insert a violation row and return its violation_id."""
    violation_id = uuid.uuid4().hex
    points = points_for(severity)
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(
            """
            INSERT INTO user_violations
                (violation_id, event_id, guild_id, user_id, category, severity, points)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (violation_id, event_id, guild_id, user_id, category, severity.value, points),
        )
        await db.commit()
    return violation_id


async def sum_points_in_window(
    guild_id: str, user_id: str, window_days: int
) -> int:
    """Sum un-revoked points in the rolling window for (guild_id, user_id)."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        cursor = await db.execute(
            """
            SELECT COALESCE(SUM(points), 0) FROM user_violations
             WHERE guild_id = ?
               AND user_id = ?
               AND revoked_at IS NULL
               AND created_at >= datetime('now', ?)
            """,
            (guild_id, user_id, f"-{window_days} days"),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0


async def count_same_category_in_window(
    guild_id: str, user_id: str, category: str, window_days: int
) -> int:
    """Count un-revoked same-category violations in the rolling window."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        cursor = await db.execute(
            """
            SELECT COUNT(*) FROM user_violations
             WHERE guild_id = ?
               AND user_id = ?
               AND category = ?
               AND revoked_at IS NULL
               AND created_at >= datetime('now', ?)
            """,
            (guild_id, user_id, category, f"-{window_days} days"),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0


async def revoke_all_for_user(guild_id: str, user_id: str) -> int:
    """Mark every active violation for a user as revoked. Returns row count."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE user_violations
               SET revoked_at = datetime('now')
             WHERE guild_id = ?
               AND user_id = ?
               AND revoked_at IS NULL
            """,
            (guild_id, user_id),
        )
        await db.commit()
        return cursor.rowcount or 0


# ---------------------------------------------------------------------------
# mod_actions
# ---------------------------------------------------------------------------


async def record_action(
    *,
    event_id: str | None,
    guild_id: str,
    user_id: str,
    action_type: ModActionType,
    actor: str,
    reason: str | None = None,
    test_mode: bool = False,
    details: str | None = None,
) -> str:
    """Insert an audit row and return its action_id."""
    action_id = uuid.uuid4().hex
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(
            """
            INSERT INTO mod_actions
                (action_id, event_id, guild_id, user_id, action_type,
                 reason, actor, test_mode, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                event_id,
                guild_id,
                user_id,
                action_type.value,
                reason,
                actor,
                1 if test_mode else 0,
                details,
            ),
        )
        await db.commit()
    return action_id


async def mark_actions_undone_for_event(event_id: str) -> int:
    """Mark every non-undo action row for this event as undone. Returns count."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE mod_actions
               SET undone_at = datetime('now')
             WHERE event_id = ?
               AND action_type != 'undo'
               AND undone_at IS NULL
            """,
            (event_id,),
        )
        await db.commit()
        return cursor.rowcount or 0


async def has_kick_for_user(guild_id: str, user_id: str) -> bool:
    """Return True if there is a real (non-test-mode, non-undone) kick on record.

    Test-mode kicks are excluded so dry-run runs don't poison the reoffense
    lookup: once test mode is turned off, real violations must not be
    escalated on the basis of a simulated kick that never actually happened.
    """
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        cursor = await db.execute(
            """
            SELECT 1 FROM mod_actions
             WHERE guild_id = ?
               AND user_id = ?
               AND action_type = 'kick'
               AND undone_at IS NULL
               AND test_mode = 0
             LIMIT 1
            """,
            (guild_id, user_id),
        )
        row = await cursor.fetchone()
        return row is not None


async def list_for_event(event_id: str) -> list[dict[str, Any]]:
    """Return audit rows for a moderation event (for the dashboard drawer)."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM mod_actions WHERE event_id = ? ORDER BY created_at ASC",
            (event_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
