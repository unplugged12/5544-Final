"""Progressive-discipline engine.

Given a moderation event that would have triggered a demo-mode auto-action,
this module decides which *escalation* to apply (warn / kick / timed_ban)
and records the ledger rows. The bot is responsible for executing the
decision on Discord (the decision is policy, the execution is plumbing).

Decision tree (order matters — first match wins):

  1. If a (guild_id, user_id) already has a non-undone kick on record and
     offends again → TIMED_BAN.
  2. If the severity-weighted point sum in the rolling window reaches the
     configured threshold → KICK.
  3. If the "repeat category kicks" policy is ON and this is at least the
     second un-revoked same-category violation in the window → KICK.
  4. Otherwise → WARN.

Only auto-actioned events feed into the engine — approved/rejected events
in the review queue are not policy decisions, they are human choices.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from models.enums import DisciplineAction, ModActionType, Severity
from repositories import discipline_repo, settings_repo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DisciplineDecision:
    """Engine output for a single event."""

    action: DisciplineAction
    reason: str
    points_total: int
    window_days: int
    test_mode: bool
    ban_minutes: int | None = None

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "points_total": self.points_total,
            "window_days": self.window_days,
            "test_mode": self.test_mode,
            "ban_minutes": self.ban_minutes,
        }


async def _load_policy() -> dict:
    """Fetch the current discipline policy from app_settings."""
    return {
        "test_mode": await settings_repo.get_bool("test_mode", False),
        "threshold": await settings_repo.get_int("discipline_points_threshold", 5),
        "window_days": await settings_repo.get_int("discipline_window_days", 30),
        "repeat_category_kicks": await settings_repo.get_bool(
            "discipline_repeat_category_kicks", True
        ),
        "ban_minutes": await settings_repo.get_int("discipline_ban_minutes", 60),
    }


async def decide_and_record(
    *,
    event_id: str,
    guild_id: str,
    user_id: str,
    category: str,
    severity: Severity,
) -> DisciplineDecision:
    """Record the violation, decide escalation, write the mod_actions row.

    This is the single entry point for the engine. Calling it:

      1. Inserts a user_violations row (points = severity weight).
      2. Computes the decision using the rolling-window query.
      3. Writes a mod_actions audit row tagged with test_mode.
      4. Returns the decision for the caller (bot) to execute.
    """
    policy = await _load_policy()

    # 1. Record the violation up front so it counts toward its own window lookup.
    await discipline_repo.add_violation(
        event_id=event_id,
        guild_id=guild_id,
        user_id=user_id,
        category=category,
        severity=severity,
    )

    # 2. Decide.
    decision = await _decide(
        guild_id=guild_id,
        user_id=user_id,
        category=category,
        policy=policy,
    )

    # 3. Audit.
    action_type = _action_type_for(decision.action)
    if action_type is not None:
        await discipline_repo.record_action(
            event_id=event_id,
            guild_id=guild_id,
            user_id=user_id,
            action_type=action_type,
            actor="bot",
            reason=decision.reason,
            test_mode=decision.test_mode,
            details=json.dumps(
                {
                    "points_total": decision.points_total,
                    "window_days": decision.window_days,
                    "ban_minutes": decision.ban_minutes,
                }
            ),
        )

    return decision


async def _decide(
    *,
    guild_id: str,
    user_id: str,
    category: str,
    policy: dict,
) -> DisciplineDecision:
    """Pure policy — no writes. Called after the violation row is inserted."""
    window_days = policy["window_days"]
    threshold = policy["threshold"]
    test_mode = policy["test_mode"]
    ban_minutes = policy["ban_minutes"]

    # Rule 1: re-offense after kick → timed ban.
    if await discipline_repo.has_kick_for_user(guild_id, user_id):
        points_total = await discipline_repo.sum_points_in_window(
            guild_id, user_id, window_days
        )
        return DisciplineDecision(
            action=DisciplineAction.TIMED_BAN,
            reason=(
                f"Re-offense after kick — applying {ban_minutes}-minute ban"
            ),
            points_total=points_total,
            window_days=window_days,
            test_mode=test_mode,
            ban_minutes=ban_minutes,
        )

    # Rule 2 & 3 share the window query.
    points_total = await discipline_repo.sum_points_in_window(
        guild_id, user_id, window_days
    )

    if points_total >= threshold:
        return DisciplineDecision(
            action=DisciplineAction.KICK,
            reason=(
                f"Severity-weighted points {points_total} ≥ threshold {threshold} "
                f"in last {window_days} days"
            ),
            points_total=points_total,
            window_days=window_days,
            test_mode=test_mode,
        )

    if policy["repeat_category_kicks"]:
        same_count = await discipline_repo.count_same_category_in_window(
            guild_id, user_id, category, window_days
        )
        if same_count >= 2:
            return DisciplineDecision(
                action=DisciplineAction.KICK,
                reason=(
                    f"Repeat {category} violation — "
                    f"{same_count} in last {window_days} days"
                ),
                points_total=points_total,
                window_days=window_days,
                test_mode=test_mode,
            )

    return DisciplineDecision(
        action=DisciplineAction.WARN,
        reason=(
            f"First-tier violation — {points_total} point(s) in last "
            f"{window_days} days"
        ),
        points_total=points_total,
        window_days=window_days,
        test_mode=test_mode,
    )


def _action_type_for(action: DisciplineAction) -> ModActionType | None:
    """Map the engine output to the audit-log action type."""
    mapping = {
        DisciplineAction.WARN: ModActionType.WARN,
        DisciplineAction.KICK: ModActionType.KICK,
        DisciplineAction.TIMED_BAN: ModActionType.TIMED_BAN,
    }
    return mapping.get(action)


async def undo_for_event(event_id: str, actor: str = "dashboard") -> dict:
    """Revoke the discipline action attached to an event.

    This is the implementation of the "Undo" button in the portal:

      1. Look up the event's (guild_id, user_id) via moderation_repo.
      2. Revoke every un-revoked violation for that user in that guild.
         Design decision (PAM): reset the whole ledger, not just this one
         row — it makes re-testing with a single Discord account trivial.
      3. Mark the mod_actions rows linked to this event as undone.
      4. Record an 'undo' action row so the audit trail is complete.

    Returns a small summary dict for the API response.
    """
    # Late import — moderation_repo pulls schemas, and that module imports this
    # one through services.__init__ in some orderings.
    from repositories import moderation_repo  # noqa: PLC0415

    event = await moderation_repo.get_by_id(event_id)
    if event is None:
        return {"undone": False, "reason": "event_not_found"}

    guild_id = getattr(event, "discord_guild_id", None)
    user_id = getattr(event, "discord_user_id", None)
    if not guild_id or not user_id:
        return {"undone": False, "reason": "no_discord_context"}

    violations_revoked = await discipline_repo.revoke_all_for_user(
        guild_id=guild_id, user_id=user_id
    )
    actions_marked = await discipline_repo.mark_actions_undone_for_event(event_id)

    await discipline_repo.record_action(
        event_id=event_id,
        guild_id=guild_id,
        user_id=user_id,
        action_type=ModActionType.UNDO,
        actor=actor,
        reason="Moderator undo via dashboard",
        test_mode=await settings_repo.get_bool("test_mode", False),
    )

    return {
        "undone": True,
        "violations_revoked": violations_revoked,
        "actions_marked_undone": actions_marked,
        "guild_id": guild_id,
        "user_id": user_id,
    }
