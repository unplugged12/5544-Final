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
    resolved_by TEXT,
    discord_user_id TEXT,
    discord_guild_id TEXT,
    discipline_action TEXT
);
CREATE INDEX IF NOT EXISTS idx_mod_events_status ON moderation_events(status);
CREATE INDEX IF NOT EXISTS idx_mod_events_created ON moderation_events(created_at DESC);
-- NOTE: idx_mod_events_user is created AFTER the ALTER TABLE ADD COLUMN
-- migration below, since the indexed columns don't exist yet on legacy DBs.

CREATE TABLE IF NOT EXISTS user_violations (
    violation_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('low','medium','high','critical')),
    points INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_user_violations_user ON user_violations(guild_id, user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS mod_actions (
    action_id TEXT PRIMARY KEY,
    event_id TEXT,
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK(action_type IN ('warn','kick','timed_ban','undo','delete_message')),
    reason TEXT,
    actor TEXT NOT NULL,
    test_mode INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    undone_at TEXT,
    details TEXT
);
CREATE INDEX IF NOT EXISTS idx_mod_actions_user ON mod_actions(guild_id, user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mod_actions_event ON mod_actions(event_id);

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

        # ------------------------------------------------------------------
        # Migration: add discord_user_id, discord_guild_id, discipline_action
        # to moderation_events on existing databases. SQLite accepts
        # ADD COLUMN for nullable TEXT without issue.
        # ------------------------------------------------------------------
        async with db.execute("PRAGMA table_info(moderation_events)") as cur:
            cols = {row[1] for row in await cur.fetchall()}
        for col_def in (
            ("discord_user_id", "TEXT"),
            ("discord_guild_id", "TEXT"),
            ("discipline_action", "TEXT"),
        ):
            name, sql_type = col_def
            if name not in cols:
                await db.execute(
                    f"ALTER TABLE moderation_events ADD COLUMN {name} {sql_type}"
                )
                logger.info("Added moderation_events.%s column", name)

        # Now that the columns definitely exist, create the composite index.
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_mod_events_user "
            "ON moderation_events(discord_guild_id, discord_user_id, created_at DESC)"
        )

        # Seed settings defaults — only inserted if the key is missing.
        _DEFAULT_SETTINGS = [
            ("demo_mode", "true"),
            ("test_mode", "false"),
            ("discipline_points_threshold", "5"),
            ("discipline_window_days", "30"),
            ("discipline_repeat_category_kicks", "true"),
            ("discipline_ban_minutes", "60"),
        ]
        for key, value in _DEFAULT_SETTINGS:
            await db.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                (key, value),
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
