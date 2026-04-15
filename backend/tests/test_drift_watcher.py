"""Tests for PR 7 — drift_watcher.check_and_warn anomaly detection.

Coverage:
  - Refusal rate > 20% over 1h window → WARNING logged
  - Avg output < 20 chars over 1h window → WARNING logged
  - Both conditions → both warnings logged
  - Neither condition → no warning
  - Empty 1h window (no chat turns) → no warning, no error
  - Window below MIN_SAMPLE_SIZE → no warning (cold start guard)
"""

from __future__ import annotations

import logging
from unittest.mock import patch, AsyncMock, MagicMock

import aiosqlite
import pytest

from database import init_db
from repositories import history_repo


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def use_test_db(db_path, _patch_db):
    """Wire every test to the temp SQLite file."""


@pytest.fixture()
async def fresh_db(db_path):
    await init_db()
    return db_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CANNED_REFUSAL = "lol nah, not doing that. wanna ask about events instead?"


async def _seed_chat_rows(turns: list[dict]) -> None:
    """Insert rows with task_type='chat' into interaction_history."""
    for i, turn in enumerate(turns):
        await history_repo.create(
            interaction_id=f"t{i}",
            task_type="chat",
            input_text="input",
            output_text=turn["output_text"],
            citations=[],
            provider_used="mock",
        )


def _get_warnings(caplog) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING
    ]


# ---------------------------------------------------------------------------
# Normal-operation tests
# ---------------------------------------------------------------------------

async def test_no_warning_when_thresholds_not_exceeded(fresh_db, caplog):
    """Low refusal rate and normal output length → no WARNING emitted."""
    # 2 refusals out of 20 turns = 10% refusal rate (below 20%)
    # avg output = len("gg nice play") = 12 chars — wait, must be >= 20
    # Use output that is >= 20 chars
    long_output = "x" * 25  # 25 chars >= 20

    turns = [{"output_text": _CANNED_REFUSAL}] * 2 + [{"output_text": long_output}] * 18
    await _seed_chat_rows(turns)

    with caplog.at_level(logging.WARNING, logger="services.drift_watcher"):
        from services import drift_watcher
        await drift_watcher.check_and_warn()

    warnings = _get_warnings(caplog)
    assert len(warnings) == 0, f"Expected no warnings, got: {warnings}"


async def test_refusal_rate_warning_when_exceeded(fresh_db, caplog):
    """Refusal rate > 20% triggers 'chat_drift: refusal_rate' WARNING."""
    # 6 refusals out of 20 = 30% (> 20%)
    long_output = "x" * 25  # keeps avg_output above 20
    turns = [{"output_text": _CANNED_REFUSAL}] * 6 + [{"output_text": long_output}] * 14
    await _seed_chat_rows(turns)

    with caplog.at_level(logging.WARNING, logger="services.drift_watcher"):
        from services import drift_watcher
        await drift_watcher.check_and_warn()

    warnings = _get_warnings(caplog)
    assert any("refusal_rate" in w for w in warnings), f"Expected refusal_rate warning, got: {warnings}"


async def test_avg_output_warning_when_below_threshold(fresh_db, caplog):
    """avg_output_chars < 20 triggers 'chat_drift: avg_output_chars' WARNING."""
    # avg = 5 chars each (well below 20)
    short_output = "y" * 5
    turns = [{"output_text": short_output}] * 20
    await _seed_chat_rows(turns)

    with caplog.at_level(logging.WARNING, logger="services.drift_watcher"):
        from services import drift_watcher
        await drift_watcher.check_and_warn()

    warnings = _get_warnings(caplog)
    assert any("avg_output_chars" in w for w in warnings), f"Expected avg_output_chars warning, got: {warnings}"


async def test_both_warnings_when_both_thresholds_exceeded(fresh_db, caplog):
    """When both conditions fire, both WARNING lines are emitted."""
    # All canned refusals (100% refusal rate) AND short output (len ~47)
    # _CANNED_REFUSAL is 47 chars — above threshold, so we need something shorter
    # Use a custom refusal phrase for this test
    short_refusal = "nope"  # 4 chars < 20, and 100% refusal if we hack the constant

    # To get short output + high refusal: use the real canned refusal for the
    # "refusal" detection but also make output short for avg detection.
    # Easiest: override _CANNED_REFUSAL in drift_watcher module for this test.
    import services.drift_watcher as dw

    turns_data = [{"output_text": "no"}] * 20  # 100% match + 2 chars avg (< 20)

    await _seed_chat_rows(turns_data)

    # Patch the imported _CANNED_REFUSAL inside drift_watcher so refusal is detected
    with (
        patch.object(dw, "_CANNED_REFUSAL", "no", create=True),
        caplog.at_level(logging.WARNING, logger="services.drift_watcher"),
    ):
        # Re-import the symbol used in check_and_warn via its local import path
        with patch("services.chat_service._CANNED_REFUSAL", "no"):
            await dw.check_and_warn()

    warnings = _get_warnings(caplog)
    assert any("refusal_rate" in w for w in warnings), f"Missing refusal_rate warning: {warnings}"
    assert any("avg_output_chars" in w for w in warnings), f"Missing avg_output_chars warning: {warnings}"


async def test_no_warning_for_empty_window(fresh_db, caplog):
    """Empty 1h window → no warning, no error."""
    # DB is fresh — no chat rows
    with caplog.at_level(logging.WARNING, logger="services.drift_watcher"):
        from services import drift_watcher
        await drift_watcher.check_and_warn()

    warnings = _get_warnings(caplog)
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(warnings) == 0
    assert len(errors) == 0


async def test_no_warning_below_min_sample_size(fresh_db, caplog):
    """Less than MIN_SAMPLE_SIZE turns in window → no check, no warning."""
    # _MIN_SAMPLE_SIZE = 5. Insert only 3 turns with bad signals.
    turns = [{"output_text": _CANNED_REFUSAL}] * 3  # 100% refusal rate, but below floor
    await _seed_chat_rows(turns)

    with caplog.at_level(logging.WARNING, logger="services.drift_watcher"):
        from services import drift_watcher
        await drift_watcher.check_and_warn()

    warnings = _get_warnings(caplog)
    assert len(warnings) == 0, f"Expected no warnings below sample floor, got: {warnings}"


async def test_no_error_on_db_failure(fresh_db, caplog):
    """DB query failure → exception logged, no unhandled exception propagated."""
    with (
        patch("aiosqlite.connect", side_effect=Exception("db offline")),
        caplog.at_level(logging.ERROR, logger="services.drift_watcher"),
    ):
        from services import drift_watcher
        # Must not raise
        await drift_watcher.check_and_warn()

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) >= 1  # The exception was logged
