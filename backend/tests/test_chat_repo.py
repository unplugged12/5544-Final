"""Tests for repositories.chat_repo — insert, load, and TTL cleanup."""

import aiosqlite
import pytest

from database import init_db
from repositories import chat_repo


# ---------------------------------------------------------------------------
# Shared async fixture: initialise the temp DB once per test.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def use_test_db(db_path, _patch_db):
    """Wire every test in this module to the temp SQLite file."""


@pytest.fixture()
async def fresh_db(db_path):
    """Initialise schema in the temp DB and return its path."""
    await init_db()
    return db_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SESSION = "sess_abc123"
_GUILD   = "g1"
_CHANNEL = "c1"
_USER    = "u1"


async def _insert(session_id=_SESSION, role="user", content="hello", ttl=60):
    return await chat_repo.insert_turn(
        session_id=session_id,
        guild_id=_GUILD,
        channel_id=_CHANNEL,
        user_id=_USER,
        role=role,
        content=content,
        ttl_minutes=ttl,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_insert_turn_returns_turn_id(fresh_db):
    turn_id = await _insert()
    assert isinstance(turn_id, str)
    assert len(turn_id) > 0


async def test_load_session_returns_inserted_turns(fresh_db, db_path):
    """Both inserted turns appear in load_session with correct field values.

    SQLite datetime('now') has second-level resolution so we can't rely on
    insertion order when both rows land in the same second.  We assert on
    the set of (role, content) pairs instead.
    """
    await _insert(role="user", content="first message")
    await _insert(role="assistant", content="first reply")

    rows = await chat_repo.load_session(_SESSION)
    assert len(rows) == 2
    pairs = {(r["role"], r["content"]) for r in rows}
    assert ("user", "first message") in pairs
    assert ("assistant", "first reply") in pairs


async def test_load_session_respects_max_turns(fresh_db, db_path):
    for i in range(8):
        await _insert(content=f"msg {i}")

    rows = await chat_repo.load_session(_SESSION, max_turns=6)
    assert len(rows) == 6


async def test_load_session_empty_for_unknown_session(fresh_db):
    rows = await chat_repo.load_session("nonexistent-session-id")
    assert rows == []


async def test_ttl_cleanup_removes_expired(fresh_db, db_path):
    """Expired turns are deleted when a new turn is inserted."""
    # Insert a turn that expires immediately (ttl=0 gives expires_at == now)
    # Force it to be in the past by writing directly to the DB
    expired_id = await _insert(content="will expire", ttl=60)

    # Back-date the expires_at so it's already expired
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE chat_turns SET expires_at = datetime('now', '-1 second') WHERE turn_id = ?",
            (expired_id,),
        )
        await db.commit()

    # Insert a fresh turn — this triggers opportunistic cleanup
    await _insert(content="stays alive", ttl=60)

    rows = await chat_repo.load_session(_SESSION)
    contents = [r["content"] for r in rows]
    assert "will expire" not in contents
    assert "stays alive" in contents
