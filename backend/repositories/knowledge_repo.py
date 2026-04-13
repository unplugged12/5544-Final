"""Repository for the knowledge_items table."""

import json
import logging

import aiosqlite

from config import settings
from models.enums import SourceType
from models.schemas import KnowledgeItem

logger = logging.getLogger(__name__)


def _row_to_item(row: aiosqlite.Row) -> KnowledgeItem:
    """Convert a database row to a KnowledgeItem model."""
    tags_raw = row["tags"]
    try:
        tags = json.loads(tags_raw) if tags_raw else []
    except (json.JSONDecodeError, TypeError):
        tags = []

    return KnowledgeItem(
        source_id=row["source_id"],
        source_type=row["source_type"],
        title=row["title"],
        content=row["content"],
        category=row["category"],
        tags=tags,
        citation_label=row["citation_label"],
        created_at=row["created_at"],
    )


async def get_all(source_type: SourceType | None = None) -> list[KnowledgeItem]:
    """Return knowledge items, optionally filtered by source_type."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")

        if source_type is not None:
            cursor = await db.execute(
                "SELECT * FROM knowledge_items WHERE source_type = ? ORDER BY source_id",
                (source_type.value,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM knowledge_items ORDER BY source_id"
            )

        rows = await cursor.fetchall()
        return [_row_to_item(row) for row in rows]


async def get_by_id(source_id: str) -> KnowledgeItem | None:
    """Return a single knowledge item by its source_id."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")

        cursor = await db.execute(
            "SELECT * FROM knowledge_items WHERE source_id = ?", (source_id,)
        )
        row = await cursor.fetchone()
        return _row_to_item(row) if row else None


async def count(source_type: SourceType | None = None) -> int:
    """Return total count of knowledge items."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        if source_type is not None:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM knowledge_items WHERE source_type = ?",
                (source_type.value,),
            )
        else:
            cursor = await db.execute("SELECT COUNT(*) FROM knowledge_items")

        row = await cursor.fetchone()
        return row[0] if row else 0
