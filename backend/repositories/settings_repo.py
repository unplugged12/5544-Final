"""Repository for the app_settings table."""

import logging

import aiosqlite

from config import settings as app_settings

logger = logging.getLogger(__name__)


async def get(key: str) -> str | None:
    """Return the value for a given settings key, or None."""
    async with aiosqlite.connect(app_settings.SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")

        cursor = await db.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None


async def set(key: str, value: str) -> None:
    """Upsert a setting value."""
    async with aiosqlite.connect(app_settings.SQLITE_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()


async def get_demo_mode() -> bool:
    """Convenience: return demo_mode as a boolean."""
    val = await get("demo_mode")
    return val == "true" if val is not None else True


async def set_demo_mode(enabled: bool) -> None:
    """Convenience: persist demo_mode."""
    await set("demo_mode", "true" if enabled else "false")


# ---------------------------------------------------------------------------
# Typed helpers
# ---------------------------------------------------------------------------


async def get_bool(key: str, default: bool) -> bool:
    val = await get(key)
    if val is None:
        return default
    return val == "true"


async def get_int(key: str, default: int) -> int:
    val = await get(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        logger.warning("app_settings.%s is not an int: %r; using default %d", key, val, default)
        return default


async def get_all() -> dict[str, str]:
    """Return every row from app_settings as a dict."""
    async with aiosqlite.connect(app_settings.SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        cursor = await db.execute("SELECT key, value FROM app_settings")
        rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}
