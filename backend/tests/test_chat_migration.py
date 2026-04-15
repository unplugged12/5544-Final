"""Migration test: existing interaction_history rows survive the CHECK rebuild.

Seeds the database with the OLD schema (no 'chat' in CHECK), runs init_db(),
then asserts:
  (a) Old rows still exist with original data.
  (b) A new INSERT with task_type='chat' succeeds (constraint updated).
"""

import aiosqlite
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_old_schema(db_path: str) -> None:
    """Create the pre-migration interaction_history and insert one legacy row."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS interaction_history (
                interaction_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL
                    CHECK(task_type IN ('faq','summary','mod_draft','moderation')),
                input_text TEXT NOT NULL,
                output_text TEXT NOT NULL,
                citations TEXT NOT NULL DEFAULT '[]',
                provider_used TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        await db.execute(
            """
            INSERT INTO interaction_history VALUES
            ('legacy-row-1', 'faq', 'What are the rules?', 'No harassment.',
             '[]', 'openai', datetime('now'))
            """
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_migration_preserves_old_rows(db_path, _patch_db):
    """Legacy rows must survive the rebuild — no data loss."""
    await _seed_old_schema(db_path)

    from database import init_db
    await init_db()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM interaction_history WHERE interaction_id = 'legacy-row-1'"
        )
        row = await cursor.fetchone()

    assert row is not None, "Legacy row was deleted during migration"
    assert row["task_type"] == "faq"
    assert row["input_text"] == "What are the rules?"
    assert row["output_text"] == "No harassment."


async def test_migration_allows_chat_task_type(db_path, _patch_db):
    """After migration, task_type='chat' must be accepted by the CHECK constraint."""
    await _seed_old_schema(db_path)

    from database import init_db
    await init_db()

    # This INSERT would violate the old CHECK constraint — must now succeed
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO interaction_history VALUES
            ('chat-row-1', 'chat', 'hey bot', 'gg, hi back',
             '[]', 'echo', datetime('now'))
            """
        )
        await db.commit()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT task_type FROM interaction_history WHERE interaction_id = 'chat-row-1'"
        )
        row = await cursor.fetchone()

    assert row is not None
    assert row["task_type"] == "chat"


async def test_migration_skipped_on_fresh_db(db_path, _patch_db):
    """On a fresh DB (no existing table) init_db must succeed with 'chat' in constraint."""
    from database import init_db
    await init_db()

    # Verify the fresh table includes 'chat' in the CHECK
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='interaction_history'"
        )
        row = await cursor.fetchone()

    assert row is not None
    assert "'chat'" in row[0]
