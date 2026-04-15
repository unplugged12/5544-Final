"""Tests for GET /api/metrics/chat — admin-gated daily chat aggregates.

Coverage:
  - No token → 401
  - Wrong token → 401
  - Correct token → 200 with expected shape
  - Sentinel default token still configured → 503
  - Returns correct daily aggregation when interaction_history is seeded
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from database import init_db
from repositories import history_repo


# ---------------------------------------------------------------------------
# DB + client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def use_test_db(db_path, _patch_db, _patch_retrieval_init):
    """Wire every test in this module to the temp SQLite file."""


@pytest.fixture()
async def seeded_client(db_path, _patch_retrieval_init):
    """Return a TestClient backed by a fresh DB (schema initialised)."""
    with patch("config.settings.SQLITE_PATH", db_path):
        from main import app
        from fastapi.testclient import TestClient

        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOOD_TOKEN = "super-secret-admin-token-abc123"
_CANNED_REFUSAL = "lol nah, not doing that. wanna ask about events instead?"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_chat_rows(db_path: str, rows: list[dict]) -> None:
    """Insert rows into interaction_history with task_type='chat'."""
    await init_db()
    for row in rows:
        await history_repo.create(
            interaction_id=row["interaction_id"],
            task_type="chat",
            input_text=row.get("input_text", "hi"),
            output_text=row.get("output_text", "gg"),
            citations=[],
            provider_used="mock",
        )


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

def test_no_token_returns_401(seeded_client):
    """Missing Authorization header → 401."""
    with patch("config.settings.CHAT_ADMIN_TOKEN", _GOOD_TOKEN):
        resp = seeded_client.get("/api/metrics/chat")
    assert resp.status_code == 401


def test_wrong_token_returns_401(seeded_client):
    """Wrong Bearer token → 401."""
    with patch("config.settings.CHAT_ADMIN_TOKEN", _GOOD_TOKEN):
        resp = seeded_client.get("/api/metrics/chat", headers=_auth("wrong-token"))
    assert resp.status_code == 401


def test_correct_token_returns_200(seeded_client):
    """Correct Bearer token → 200 with expected response shape."""
    with patch("config.settings.CHAT_ADMIN_TOKEN", _GOOD_TOKEN):
        resp = seeded_client.get("/api/metrics/chat", headers=_auth(_GOOD_TOKEN))
    assert resp.status_code == 200
    body = resp.json()
    assert "days" in body
    assert "totals" in body
    assert "note" in body
    assert isinstance(body["days"], list)


def test_sentinel_token_returns_503(seeded_client):
    """If CHAT_ADMIN_TOKEN is still the sentinel, endpoint returns 503."""
    with patch("config.settings.CHAT_ADMIN_TOKEN", "REPLACE_ME_WITH_ADMIN_TOKEN"):
        resp = seeded_client.get("/api/metrics/chat", headers=_auth("anything"))
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Aggregation tests
# ---------------------------------------------------------------------------

async def test_empty_db_returns_zero_totals(db_path, seeded_client):
    """With no chat rows, totals are all zero and days list is empty."""
    await init_db()
    with patch("config.settings.CHAT_ADMIN_TOKEN", _GOOD_TOKEN):
        resp = seeded_client.get("/api/metrics/chat", headers=_auth(_GOOD_TOKEN))
    assert resp.status_code == 200
    body = resp.json()
    assert body["totals"]["turns"] == 0
    assert body["totals"]["refusals"] == 0
    assert body["days"] == []


async def test_daily_aggregation_counts_turns(db_path, seeded_client):
    """Turn counts are correct when interaction_history has chat rows."""
    await _seed_chat_rows(db_path, [
        {"interaction_id": "id1", "output_text": "gg"},
        {"interaction_id": "id2", "output_text": "nice play"},
        {"interaction_id": "id3", "output_text": _CANNED_REFUSAL},
    ])

    with patch("config.settings.CHAT_ADMIN_TOKEN", _GOOD_TOKEN):
        resp = seeded_client.get("/api/metrics/chat", headers=_auth(_GOOD_TOKEN))

    assert resp.status_code == 200
    body = resp.json()
    assert body["totals"]["turns"] == 3
    assert body["totals"]["refusals"] == 1


async def test_response_shape_has_expected_fields(db_path, seeded_client):
    """Each day entry has date, turns, refusals, input_tokens, output_tokens."""
    await _seed_chat_rows(db_path, [
        {"interaction_id": "x1", "output_text": "ok"},
    ])

    with patch("config.settings.CHAT_ADMIN_TOKEN", _GOOD_TOKEN):
        resp = seeded_client.get("/api/metrics/chat", headers=_auth(_GOOD_TOKEN))

    body = resp.json()
    assert len(body["days"]) == 1
    day = body["days"][0]
    assert "date" in day
    assert "turns" in day
    assert "refusals" in day
    assert "input_tokens" in day   # null — tokens not in audit table
    assert "output_tokens" in day  # null — tokens not in audit table


async def test_non_chat_rows_excluded(db_path, seeded_client):
    """Rows with task_type != 'chat' must not count toward chat metrics."""
    await init_db()
    # Insert a non-chat row directly via history_repo
    await history_repo.create(
        interaction_id="faq1",
        task_type="faq",
        input_text="q",
        output_text="a",
        citations=[],
        provider_used="mock",
    )

    with patch("config.settings.CHAT_ADMIN_TOKEN", _GOOD_TOKEN):
        resp = seeded_client.get("/api/metrics/chat", headers=_auth(_GOOD_TOKEN))

    body = resp.json()
    assert body["totals"]["turns"] == 0


async def test_refusal_count_correct(db_path, seeded_client):
    """Refusal count is exactly the number of rows matching the canned refusal phrase."""
    await _seed_chat_rows(db_path, [
        {"interaction_id": "r1", "output_text": _CANNED_REFUSAL},
        {"interaction_id": "r2", "output_text": _CANNED_REFUSAL},
        {"interaction_id": "r3", "output_text": "gg nice"},
    ])

    with patch("config.settings.CHAT_ADMIN_TOKEN", _GOOD_TOKEN):
        resp = seeded_client.get("/api/metrics/chat", headers=_auth(_GOOD_TOKEN))

    body = resp.json()
    assert body["totals"]["refusals"] == 2
    assert body["totals"]["turns"] == 3
