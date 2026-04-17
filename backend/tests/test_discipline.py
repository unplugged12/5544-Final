"""Unit tests for the progressive-discipline engine.

Exercises the decision tree branches end-to-end against a real (temp-file)
SQLite DB:

  - first violation  → WARN
  - second same-category → KICK
  - severity-weighted points >= threshold → KICK
  - re-offense after kick → TIMED_BAN
  - undo resets the ledger and marks prior action rows undone
  - test_mode flag flows through to the audit row
"""

from __future__ import annotations

import aiosqlite
import pytest

from database import init_db
from models.enums import (
    DisciplineAction,
    EventSource,
    ModerationStatus,
    Severity,
    SuggestedAction,
    ViolationType,
)
from repositories import discipline_repo, moderation_repo, settings_repo
from services import discipline_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def seeded_db(db_path, _patch_db):
    """Initialise a fresh DB with the discipline defaults seeded."""
    await init_db()
    yield db_path


GUILD = "10000000000000001"
USER = "20000000000000001"


async def _insert_event(
    *,
    event_id: str,
    severity: Severity = Severity.MEDIUM,
    violation: ViolationType = ViolationType.HARASSMENT,
    guild_id: str = GUILD,
    user_id: str = USER,
    source: EventSource = EventSource.DISCORD,
) -> str:
    await moderation_repo.create(
        event_id=event_id,
        message_content="<test message>",
        violation_type=violation,
        matched_rule="Rule test",
        explanation="testing",
        severity=severity,
        suggested_action=SuggestedAction.REMOVE_MESSAGE,
        status=ModerationStatus.AUTO_ACTIONED,
        source=source,
        discord_user_id=user_id,
        discord_guild_id=guild_id,
    )
    return event_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_violation_warns(seeded_db):
    await _insert_event(event_id="ev1", severity=Severity.LOW)
    decision = await discipline_service.decide_and_record(
        event_id="ev1",
        guild_id=GUILD,
        user_id=USER,
        category=ViolationType.HARASSMENT.value,
        severity=Severity.LOW,
    )
    assert decision.action == DisciplineAction.WARN
    assert decision.points_total == 1  # low = 1 point
    assert decision.test_mode is False


@pytest.mark.asyncio
async def test_second_same_category_kicks(seeded_db):
    await _insert_event(event_id="ev1", severity=Severity.LOW)
    d1 = await discipline_service.decide_and_record(
        event_id="ev1",
        guild_id=GUILD,
        user_id=USER,
        category=ViolationType.HARASSMENT.value,
        severity=Severity.LOW,
    )
    assert d1.action == DisciplineAction.WARN

    await _insert_event(event_id="ev2", severity=Severity.LOW)
    d2 = await discipline_service.decide_and_record(
        event_id="ev2",
        guild_id=GUILD,
        user_id=USER,
        category=ViolationType.HARASSMENT.value,
        severity=Severity.LOW,
    )
    assert d2.action == DisciplineAction.KICK
    assert "Repeat harassment" in d2.reason


@pytest.mark.asyncio
async def test_severity_threshold_triggers_kick(seeded_db):
    # A single CRITICAL severity violation (5 points) should hit the
    # default threshold (5) on its own — no repeat required.
    await _insert_event(event_id="evA", severity=Severity.CRITICAL)
    decision = await discipline_service.decide_and_record(
        event_id="evA",
        guild_id=GUILD,
        user_id=USER,
        category=ViolationType.HATE_SPEECH.value,
        severity=Severity.CRITICAL,
    )
    assert decision.action == DisciplineAction.KICK
    assert decision.points_total == 5
    assert "threshold" in decision.reason


@pytest.mark.asyncio
async def test_reoffense_after_kick_bans(seeded_db):
    # First: accumulate a critical violation → KICK
    await _insert_event(event_id="evA", severity=Severity.CRITICAL)
    kick = await discipline_service.decide_and_record(
        event_id="evA",
        guild_id=GUILD,
        user_id=USER,
        category=ViolationType.HATE_SPEECH.value,
        severity=Severity.CRITICAL,
    )
    assert kick.action == DisciplineAction.KICK

    # Second: same user offends again → TIMED_BAN (regardless of category/severity)
    await _insert_event(event_id="evB", severity=Severity.LOW)
    ban = await discipline_service.decide_and_record(
        event_id="evB",
        guild_id=GUILD,
        user_id=USER,
        category=ViolationType.SPAM.value,
        severity=Severity.LOW,
    )
    assert ban.action == DisciplineAction.TIMED_BAN
    assert ban.ban_minutes == 60  # default


@pytest.mark.asyncio
async def test_undo_resets_ledger(seeded_db):
    """Undo should revoke all violations and mark the kick row undone."""
    await _insert_event(event_id="evA", severity=Severity.CRITICAL)
    await discipline_service.decide_and_record(
        event_id="evA",
        guild_id=GUILD,
        user_id=USER,
        category=ViolationType.HATE_SPEECH.value,
        severity=Severity.CRITICAL,
    )

    # Sanity: kick is on record
    assert await discipline_repo.has_kick_for_user(GUILD, USER) is True

    result = await discipline_service.undo_for_event("evA")
    assert result["undone"] is True
    assert result["violations_revoked"] >= 1
    assert result["actions_marked_undone"] >= 1

    # Ledger should now be empty and no active kick
    assert await discipline_repo.sum_points_in_window(GUILD, USER, 30) == 0
    assert await discipline_repo.has_kick_for_user(GUILD, USER) is False


@pytest.mark.asyncio
async def test_undo_missing_event_returns_reason(seeded_db):
    result = await discipline_service.undo_for_event("nonexistent")
    assert result == {"undone": False, "reason": "event_not_found"}


@pytest.mark.asyncio
async def test_undo_no_discord_context_returns_reason(seeded_db):
    # Dashboard-sourced event with no Discord IDs — nothing to undo against.
    await moderation_repo.create(
        event_id="dash1",
        message_content="<test>",
        violation_type=ViolationType.HARASSMENT,
        matched_rule=None,
        explanation="x",
        severity=Severity.LOW,
        suggested_action=SuggestedAction.REMOVE_MESSAGE,
        status=ModerationStatus.AUTO_ACTIONED,
        source=EventSource.DASHBOARD,
    )
    result = await discipline_service.undo_for_event("dash1")
    assert result == {"undone": False, "reason": "no_discord_context"}


@pytest.mark.asyncio
async def test_test_mode_flag_is_recorded(seeded_db):
    await settings_repo.set("test_mode", "true")
    await _insert_event(event_id="ev1", severity=Severity.LOW)
    decision = await discipline_service.decide_and_record(
        event_id="ev1",
        guild_id=GUILD,
        user_id=USER,
        category=ViolationType.HARASSMENT.value,
        severity=Severity.LOW,
    )
    assert decision.test_mode is True

    # The recorded mod_actions row should carry test_mode=1
    async with aiosqlite.connect(seeded_db) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT test_mode FROM mod_actions WHERE event_id = 'ev1'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["test_mode"] == 1


@pytest.mark.asyncio
async def test_test_mode_kick_does_not_escalate_after_flip(seeded_db):
    """A test-mode (simulated) kick must not trigger a real timed-ban later.

    Regression: has_kick_for_user used to look at every non-undone kick row,
    so dry-run runs in test mode would poison the reoffense lookup once
    test mode was turned off.
    """
    # Test mode ON: first violation escalates to a (simulated) KICK.
    await settings_repo.set("test_mode", "true")
    await _insert_event(event_id="ev_sim", severity=Severity.CRITICAL)
    sim = await discipline_service.decide_and_record(
        event_id="ev_sim",
        guild_id=GUILD,
        user_id=USER,
        category=ViolationType.HATE_SPEECH.value,
        severity=Severity.CRITICAL,
    )
    assert sim.action == DisciplineAction.KICK
    assert sim.test_mode is True

    # Flip test mode OFF. Next offense should NOT see the simulated kick.
    await settings_repo.set("test_mode", "false")
    assert await discipline_repo.has_kick_for_user(GUILD, USER) is False

    # Undo the first simulated ledger so we can observe a clean WARN path.
    await discipline_service.undo_for_event("ev_sim")

    await _insert_event(event_id="ev_real", severity=Severity.LOW)
    real = await discipline_service.decide_and_record(
        event_id="ev_real",
        guild_id=GUILD,
        user_id=USER,
        category=ViolationType.SPAM.value,
        severity=Severity.LOW,
    )
    # Without the test-mode-aware filter this would be TIMED_BAN.
    assert real.action == DisciplineAction.WARN


@pytest.mark.asyncio
async def test_repeat_category_policy_can_be_disabled(seeded_db):
    await settings_repo.set("discipline_repeat_category_kicks", "false")

    await _insert_event(event_id="ev1", severity=Severity.LOW)
    d1 = await discipline_service.decide_and_record(
        event_id="ev1",
        guild_id=GUILD,
        user_id=USER,
        category=ViolationType.HARASSMENT.value,
        severity=Severity.LOW,
    )
    assert d1.action == DisciplineAction.WARN

    await _insert_event(event_id="ev2", severity=Severity.LOW)
    d2 = await discipline_service.decide_and_record(
        event_id="ev2",
        guild_id=GUILD,
        user_id=USER,
        category=ViolationType.HARASSMENT.value,
        severity=Severity.LOW,
    )
    # Two points total, threshold still 5 — should still WARN, not KICK
    assert d2.action == DisciplineAction.WARN
