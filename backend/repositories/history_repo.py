"""Repository for the interaction_history table."""

import json
import logging

import aiosqlite

from config import settings

logger = logging.getLogger(__name__)


async def create(
    *,
    interaction_id: str,
    task_type: str,
    input_text: str,
    output_text: str,
    citations: list[dict],
    provider_used: str,
) -> None:
    """Insert a new interaction record."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(
            """
            INSERT INTO interaction_history
                (interaction_id, task_type, input_text, output_text, citations, provider_used)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                interaction_id,
                task_type,
                input_text,
                output_text,
                json.dumps(citations),
                provider_used,
            ),
        )
        await db.commit()


async def list_interactions(
    limit: int = 50, offset: int = 0
) -> tuple[list[dict], int]:
    """Return paginated interactions ordered by created_at DESC."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")

        cursor = await db.execute("SELECT COUNT(*) FROM interaction_history")
        total_row = await cursor.fetchone()
        total = total_row[0] if total_row else 0

        cursor = await db.execute(
            "SELECT * FROM interaction_history ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()

        items = []
        for row in rows:
            items.append(
                {
                    "interaction_id": row["interaction_id"],
                    "task_type": row["task_type"],
                    "input_text": row["input_text"],
                    "output_text": row["output_text"],
                    "citations": json.loads(row["citations"]),
                    "provider_used": row["provider_used"],
                    "created_at": row["created_at"],
                }
            )

        return items, total
