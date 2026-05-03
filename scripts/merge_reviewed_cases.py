"""Merge approved review-queue rows into ``data/eval/eval_moderation.json``.

Reads ``data/eval/eval_moderation_review_queue.csv`` and folds rows where
``reviewer_decision`` is ``approved`` (or ``edited`` with JSON overrides in
``reviewer_edits``) into the canonical eval JSON. Idempotent: rows whose
``proposed_case_id`` already exists in the JSON are skipped, so re-running
after partial review is safe.

Usage:

    python scripts/merge_reviewed_cases.py
    python scripts/merge_reviewed_cases.py --csv data/eval/eval_moderation_review_queue.csv
    python scripts/merge_reviewed_cases.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = REPO_ROOT / "data" / "eval" / "eval_moderation_review_queue.csv"
EVAL_JSON = REPO_ROOT / "data" / "eval" / "eval_moderation.json"

ALLOWED_VIOLATION_TYPES = {
    "spam",
    "harassment",
    "hate_speech",
    "toxic_attack",
    "self_promo",
    "spoiler",
    "flooding",
    "no_violation",
}
ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}
ALLOWED_ACTIONS = {
    "no_action",
    "warn",
    "remove_message",
    "timeout_or_mute_recommendation",
    "escalate_to_human",
}
ALLOWED_CATEGORIES = {
    "clear_violation",
    "near_miss",
    "false_positive_bait",
    "sarcasm",
    "gaming_vernacular",
    "ambiguous",
    "benign",
}
RULE_ID_PATTERN = re.compile(r"^rule_\d{3}$")


def load_rule_ids() -> set[str]:
    rules_path = REPO_ROOT / "data" / "seed" / "rules.json"
    with open(rules_path, "r", encoding="utf-8") as f:
        return {r["source_id"] for r in json.load(f)["rules"]}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", type=str, default=str(DEFAULT_CSV))
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be merged without writing the JSON.",
    )
    return p.parse_args()


def coerce_row(row: dict[str, str]) -> dict[str, Any]:
    """Translate a CSV row into the canonical eval-record schema."""
    rule = (row.get("proposed_rule_match") or "").strip()
    record: dict[str, Any] = {
        "case_id": (row.get("proposed_case_id") or "").strip(),
        "content": row.get("content", ""),
        "expected_violation_type": (row.get("proposed_violation_type") or "").strip(),
        "expected_severity": (row.get("proposed_severity") or "").strip(),
        "expected_rule_match": rule if rule else None,
        "category": (row.get("category") or "").strip(),
        "expected_suggested_action": (
            row.get("proposed_suggested_action")
            or row.get("expected_suggested_action")
            or ""
        ).strip(),
        "notes": row.get("notes", ""),
        "channel_context": (row.get("channel_context") or "").strip(),
    }
    # The generation script doesn't populate proposed_suggested_action separately,
    # so allow it to come through reviewer_edits (below) or default to no_action
    # for benign no_violation rows. Validation later catches any blanks.
    if not record["expected_suggested_action"]:
        if record["expected_violation_type"] == "no_violation":
            record["expected_suggested_action"] = "no_action"
    return record


def apply_edits(record: dict[str, Any], edits_raw: str) -> dict[str, Any]:
    edits_raw = (edits_raw or "").strip()
    if not edits_raw:
        return record
    try:
        edits = json.loads(edits_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"reviewer_edits is not valid JSON: {edits_raw!r}") from exc
    if not isinstance(edits, dict):
        raise ValueError(f"reviewer_edits must be a JSON object, got {type(edits).__name__}")
    record.update(edits)
    return record


def validate(record: dict[str, Any], rule_ids: set[str]) -> list[str]:
    errors: list[str] = []
    if not record.get("case_id"):
        errors.append("missing case_id")
    if not record.get("content"):
        errors.append("missing content")
    if record.get("expected_violation_type") not in ALLOWED_VIOLATION_TYPES:
        errors.append(f"bad expected_violation_type: {record.get('expected_violation_type')!r}")
    if record.get("expected_severity") not in ALLOWED_SEVERITIES:
        errors.append(f"bad expected_severity: {record.get('expected_severity')!r}")
    if record.get("expected_suggested_action") not in ALLOWED_ACTIONS:
        errors.append(f"bad expected_suggested_action: {record.get('expected_suggested_action')!r}")
    if record.get("category") not in ALLOWED_CATEGORIES:
        errors.append(f"bad category: {record.get('category')!r}")
    rule = record.get("expected_rule_match")
    if rule is not None:
        if not isinstance(rule, str) or not RULE_ID_PATTERN.match(rule):
            errors.append(f"bad expected_rule_match format: {rule!r}")
        elif rule not in rule_ids:
            errors.append(f"unknown expected_rule_match: {rule!r}")
    return errors


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Review-queue CSV not found at {csv_path}.")
        print("Run scripts/generate_eval_cases.py first.")
        return 1
    if not EVAL_JSON.exists():
        print(f"Canonical eval JSON not found at {EVAL_JSON}.")
        return 1

    rule_ids = load_rule_ids()

    with open(EVAL_JSON, "r", encoding="utf-8") as f:
        eval_data = json.load(f)
    existing_cases: list[dict[str, Any]] = eval_data.get("eval_moderation", [])
    existing_ids: set[str] = {c["case_id"] for c in existing_cases}

    approved_to_add: list[dict[str, Any]] = []
    skipped_existing = 0
    skipped_rejected = 0
    rejected_invalid = 0

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            decision = (row.get("reviewer_decision") or "").strip().lower()
            if decision not in {"approved", "edited"}:
                if decision in {"rejected", ""}:
                    skipped_rejected += 1
                continue

            case_id = (row.get("proposed_case_id") or "").strip()
            if not case_id:
                rejected_invalid += 1
                print(f"[skip] row has no proposed_case_id: {row}")
                continue
            if case_id in existing_ids:
                skipped_existing += 1
                continue

            record = coerce_row(row)
            try:
                if decision == "edited":
                    record = apply_edits(record, row.get("reviewer_edits", ""))
            except ValueError as exc:
                rejected_invalid += 1
                print(f"[skip] {case_id}: {exc}")
                continue

            errors = validate(record, rule_ids)
            if errors:
                rejected_invalid += 1
                print(f"[skip] {case_id}: {'; '.join(errors)}")
                continue

            approved_to_add.append(record)
            existing_ids.add(case_id)

    print()
    print(f"Approved & ready to merge: {len(approved_to_add)}")
    print(f"Already in JSON (idempotent skip): {skipped_existing}")
    print(f"Rejected / unreviewed rows skipped: {skipped_rejected}")
    print(f"Invalid rows skipped: {rejected_invalid}")

    if not approved_to_add:
        print("Nothing to merge.")
        return 0

    if args.dry_run:
        print("\n[dry-run] not writing JSON. First proposed merge:")
        print(json.dumps(approved_to_add[0], indent=2))
        return 0

    eval_data["eval_moderation"] = existing_cases + approved_to_add
    with open(EVAL_JSON, "w", encoding="utf-8") as f:
        json.dump(eval_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {len(eval_data['eval_moderation'])} total cases to {EVAL_JSON}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
