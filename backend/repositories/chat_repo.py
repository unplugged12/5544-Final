"""Repository for chat_turns table — short-term session history.

Turns are keyed by session_id = sha256(guild_id|channel_id|user_id)[:16].
Opportunistic TTL cleanup runs on every write so the table stays small
without a background job (sufficient at class-project scale).
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

import aiosqlite

from config import settings

logger = logging.getLogger(__name__)


async def insert_turn(
    *,
    session_id: str,
    guild_id: str,
    channel_id: str,
    user_id: str,
    role: str,
    content: str,
    ttl_minutes: int,
) -> str:
    """Insert a chat turn and return its turn_id.

    Runs opportunistic TTL cleanup before the insert so expired rows are
    removed on every write path rather than accumulating indefinitely.
    """
    turn_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=ttl_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        # Opportunistic TTL cleanup on every write
        await db.execute("DELETE FROM chat_turns WHERE expires_at <= datetime('now')")
        await db.execute(
            """
            INSERT INTO chat_turns
                (turn_id, session_id, guild_id, channel_id, user_id,
                 role, content, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                turn_id,
                session_id,
                guild_id,
                channel_id,
                user_id,
                role,
                content,
                created_at,
                expires_at,
            ),
        )
        await db.commit()

    logger.debug("Inserted chat turn %s for session %s", turn_id, session_id)
    return turn_id


async def load_session(session_id: str, max_turns: int = 6) -> list[dict]:
    """Return up to *max_turns* non-expired turns for *session_id*, oldest first."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        cursor = await db.execute(
            """
            SELECT role, content, created_at
            FROM chat_turns
            WHERE session_id = ? AND expires_at > datetime('now')
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (session_id, max_turns),
        )
        rows = await cursor.fetchall()

    return [dict(r) for r in rows]
