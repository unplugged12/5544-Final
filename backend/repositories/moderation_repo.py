"""Repository for the moderation_events table."""

import logging
from datetime import datetime, timezone

import aiosqlite

from config import settings
from models.enums import (
    EventSource,
    ModerationStatus,
    Severity,
    SuggestedAction,
    ViolationType,
)
from models.schemas import ModerationEventResponse

logger = logging.getLogger(__name__)


def _row_to_event(row: aiosqlite.Row) -> ModerationEventResponse:
    """Map a DB row to a ModerationEventResponse."""
    # aiosqlite.Row supports keys() lookup; use .get-style with try/except to
    # stay robust against old rows from before the discipline columns existed.
    def _maybe(col: str) -> str | None:
        try:
            return row[col]
        except (IndexError, KeyError):
            return None

    return ModerationEventResponse(
        event_id=row["event_id"],
        message_content=row["message_content"],
        violation_type=row["violation_type"],
        matched_rule=row["matched_rule"],
        explanation=row["explanation"],
        severity=row["severity"],
        suggested_action=row["suggested_action"],
        status=row["status"],
        source=row["source"],
        created_at=row["created_at"],
        resolved_at=row["resolved_at"],
        resolved_by=row["resolved_by"],
        discord_user_id=_maybe("discord_user_id"),
        discord_guild_id=_maybe("discord_guild_id"),
        discipline_action=_maybe("discipline_action"),
    )


async def create(
    *,
    event_id: str,
    message_content: str,
    violation_type: ViolationType,
    matched_rule: str | None,
    explanation: str,
    severity: Severity,
    suggested_action: SuggestedAction,
    status: ModerationStatus,
    source: EventSource,
    discord_user_id: str | None = None,
    discord_guild_id: str | None = None,
) -> ModerationEventResponse:
    """Insert a new moderation event and return it."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")

        await db.execute(
            """
            INSERT INTO moderation_events
                (event_id, message_content, violation_type, matched_rule,
                 explanation, severity, suggested_action, status, source,
                 discord_user_id, discord_guild_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                message_content,
                violation_type.value,
                matched_rule,
                explanation,
                severity.value,
                suggested_action.value,
                status.value,
                source.value,
                discord_user_id,
                discord_guild_id,
            ),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM moderation_events WHERE event_id = ?", (event_id,)
        )
        row = await cursor.fetchone()
        return _row_to_event(row)


async def set_discipline_action(event_id: str, action: str) -> None:
    """Persist the discipline-engine decision on the event row."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(
            "UPDATE moderation_events SET discipline_action = ? WHERE event_id = ?",
            (action, event_id),
        )
        await db.commit()


async def get_by_id(event_id: str) -> ModerationEventResponse | None:
    """Return a single event by its event_id."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")

        cursor = await db.execute(
            "SELECT * FROM moderation_events WHERE event_id = ?", (event_id,)
        )
        row = await cursor.fetchone()
        return _row_to_event(row) if row else None


async def update_status(
    event_id: str,
    status: ModerationStatus,
    resolved_by: str | None = "dashboard",
) -> ModerationEventResponse | None:
    """Set the status, resolved_at, and resolved_by on an event."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")

        await db.execute(
            """
            UPDATE moderation_events
               SET status = ?, resolved_at = ?, resolved_by = ?
             WHERE event_id = ?
            """,
            (status.value, now, resolved_by, event_id),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM moderation_events WHERE event_id = ?", (event_id,)
        )
        row = await cursor.fetchone()
        return _row_to_event(row) if row else None


async def list_events(
    limit: int = 50, offset: int = 0, status: str | None = None
) -> tuple[list[ModerationEventResponse], int]:
    """Return paginated events ordered by created_at DESC, plus total count."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")

        where_clause = ""
        params: list = []
        if status:
            where_clause = " WHERE status = ?"
            params.append(status)

        # Total count
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM moderation_events{where_clause}", params
        )
        total_row = await cursor.fetchone()
        total = total_row[0] if total_row else 0

        # Paginated results
        cursor = await db.execute(
            f"SELECT * FROM moderation_events{where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        rows = await cursor.fetchall()
        events = [_row_to_event(row) for row in rows]

        return events, total
