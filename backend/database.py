"""Async SQLite helpers using aiosqlite.

Every public function opens its own connection — no module-level handle.
"""

import logging

import aiosqlite

from config import settings

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS knowledge_items (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL CHECK(source_type IN ('rule','faq','announcement','mod_note')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    citation_label TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_knowledge_source_type ON knowledge_items(source_type);

CREATE TABLE IF NOT EXISTS moderation_events (
    event_id TEXT PRIMARY KEY,
    message_content TEXT NOT NULL,
    violation_type TEXT NOT NULL,
    matched_rule TEXT,
    explanation TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('low','medium','high','critical')),
    suggested_action TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','auto_actioned')),
    source TEXT NOT NULL DEFAULT 'dashboard' CHECK(source IN ('discord','dashboard')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    resolved_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_mod_events_status ON moderation_events(status);
CREATE INDEX IF NOT EXISTS idx_mod_events_created ON moderation_events(created_at DESC);

CREATE TABLE IF NOT EXISTS interaction_history (
    interaction_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL CHECK(task_type IN ('faq','summary','mod_draft','moderation','chat')),
    input_text TEXT NOT NULL,
    output_text TEXT NOT NULL,
    citations TEXT NOT NULL DEFAULT '[]',
    provider_used TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_turns (
    turn_id     TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    guild_id    TEXT NOT NULL,
    channel_id  TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    role        TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_session_time
    ON chat_turns(session_id, created_at DESC);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


async def init_db() -> None:
    """Create tables and seed defaults.  Called once at startup."""
    logger.info("Initializing database at %s", settings.SQLITE_PATH)
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        # ------------------------------------------------------------------
        # Migration: rebuild interaction_history CHECK constraint to include
        # 'chat'.  SQLite does not support ALTER TABLE ... MODIFY COLUMN, so
        # we must rename → recreate → copy → drop.
        # On failure we preserve the _old table and log — startup continues.
        # ------------------------------------------------------------------
        try:
            async with db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='interaction_history'"
            ) as cur:
                row = await cur.fetchone()
            if row is not None and "'chat'" not in row[0]:
                logger.info(
                    "Migrating interaction_history CHECK constraint to include 'chat'"
                )
                await db.executescript("""
                    ALTER TABLE interaction_history RENAME TO interaction_history_old;
                    CREATE TABLE interaction_history (
                        interaction_id TEXT PRIMARY KEY,
                        task_type TEXT NOT NULL CHECK(task_type IN ('faq','summary','mod_draft','moderation','chat')),
                        input_text TEXT NOT NULL,
                        output_text TEXT NOT NULL,
                        citations TEXT NOT NULL DEFAULT '[]',
                        provider_used TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );
                    INSERT INTO interaction_history SELECT * FROM interaction_history_old;
                    DROP TABLE interaction_history_old;
                """)
                await db.commit()
                logger.info("interaction_history migration complete")
        except Exception:
            logger.exception(
                "interaction_history migration failed — _old table preserved; "
                "manual intervention required"
            )

        await db.executescript(_DDL)
        await db.execute(
            "INSERT OR IGNORE INTO app_settings VALUES ('demo_mode', 'true')"
        )
        await db.commit()
    logger.info("Database initialized successfully")


async def get_db() -> aiosqlite.Connection:
    """Return a new connection with WAL mode and Row factory.

    Callers are responsible for closing it — prefer using this inside
    ``async with aiosqlite.connect(...) as db:`` in route / service code,
    but this helper is provided for convenience when a bare connection is
    needed.
    """
    db = await aiosqlite.connect(settings.SQLITE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db
