"""Generate additional eval cases via Claude (one-off, Phase B.1).

Reads the 60 hand-authored anchors in ``data/eval/eval_moderation.json`` plus
``data/seed/rules.json`` and asks Claude to produce 5 new cases per applicable
``(rule x category)`` cell, targeting roughly 120 generated cases. Output goes
to a CSV review queue at ``data/eval/eval_moderation_review_queue.csv`` for
manual human approval - **the script never auto-merges into the dataset**.

Usage:

    # Dry-run: print prompts only (no API calls).
    python scripts/generate_eval_cases.py --dry-run

    # Real run (requires ANTHROPIC_API_KEY).
    python scripts/generate_eval_cases.py

    # Re-run only specific rule cells.
    python scripts/generate_eval_cases.py --rules rule_006,rule_008

After the script writes the CSV, open it, set ``reviewer_decision`` to one of
``approved | rejected | edited`` for each row, optionally adjust fields via
``reviewer_edits`` (JSON object with overrides), then run::

    python scripts/merge_reviewed_cases.py

to fold approved rows into ``data/eval/eval_moderation.json``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = REPO_ROOT / "data" / "seed" / "rules.json"
ANCHORS_PATH = REPO_ROOT / "data" / "eval" / "eval_moderation.json"
OUT_CSV = REPO_ROOT / "data" / "eval" / "eval_moderation_review_queue.csv"

# Categories the reviewer expects for each rule. Cells that don't make sense
# (e.g., gaming_vernacular for NSFW Rule 11) are pruned so we don't waste
# API budget on nonsense generations.
DEFAULT_CATEGORIES_PER_RULE: dict[str, list[str]] = {
    "rule_001": ["clear_violation", "near_miss", "false_positive_bait", "gaming_vernacular"],
    "rule_002": ["clear_violation", "near_miss"],
    "rule_003": ["clear_violation", "near_miss", "false_positive_bait"],
    "rule_004": ["clear_violation", "near_miss", "benign", "ambiguous"],
    "rule_005": ["clear_violation", "near_miss", "ambiguous"],
    "rule_006": ["clear_violation", "near_miss", "benign", "ambiguous"],
    "rule_007": ["clear_violation", "near_miss"],
    "rule_008": ["clear_violation", "near_miss", "benign", "ambiguous"],
    "rule_009": ["clear_violation", "near_miss"],
    "rule_010": ["clear_violation", "near_miss", "ambiguous"],
    "rule_011": ["clear_violation", "near_miss"],
    "rule_012": ["clear_violation", "near_miss"],
    "rule_013": ["clear_violation", "near_miss"],
    "rule_014": ["clear_violation", "near_miss", "benign"],
    "rule_015": ["clear_violation", "near_miss"],
    "rule_016": ["clear_violation", "near_miss"],
    "rule_017": ["clear_violation", "near_miss"],
    "rule_018": ["clear_violation", "near_miss"],
}

CASES_PER_CELL = 5
MODEL = "claude-sonnet-4-6"  # Sonnet is plenty for dataset generation; cheaper than Opus. Eval results cache by model+prompt.
MAX_TOKENS = 2000

CSV_FIELDS = [
    "proposed_case_id",
    "content",
    "proposed_violation_type",
    "proposed_severity",
    "proposed_rule_match",
    "proposed_suggested_action",
    "category",
    "notes",
    "channel_context",
    "reviewer_decision",
    "reviewer_edits",
]


def load_rules() -> list[dict[str, Any]]:
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["rules"]


def load_anchors() -> list[dict[str, Any]]:
    with open(ANCHORS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["eval_moderation"]


def pick_anchor_examples(
    anchors: list[dict[str, Any]],
    rule_id: str,
    category: str,
    max_examples: int = 3,
) -> list[dict[str, Any]]:
    """Return up to ``max_examples`` anchors matching this (rule, category) cell.

    Falls back to anchors matching just the rule if the cell is empty, then to
    any anchors in the same category. This keeps the prompt grounded.
    """

    exact = [
        a for a in anchors
        if a.get("expected_rule_match") == rule_id and a.get("category") == category
    ]
    if len(exact) >= max_examples:
        return exact[:max_examples]

    by_rule = [a for a in anchors if a.get("expected_rule_match") == rule_id]
    by_cat = [a for a in anchors if a.get("category") == category]
    pool = exact + [a for a in by_rule if a not in exact] + [a for a in by_cat if a not in exact and a not in by_rule]
    return pool[:max_examples]


def build_prompt(rule: dict[str, Any], category: str, examples: list[dict[str, Any]]) -> str:
    rule_id = rule["source_id"]
    examples_block = json.dumps(
        [
            {
                "content": e["content"],
                "expected_violation_type": e["expected_violation_type"],
                "expected_severity": e["expected_severity"],
                "expected_rule_match": e["expected_rule_match"],
                "category": e["category"],
                "expected_suggested_action": e["expected_suggested_action"],
                "notes": e.get("notes", ""),
                "channel_context": e.get("channel_context", "general"),
            }
            for e in examples
        ],
        indent=2,
    )

    return f"""You are generating labeled evaluation cases for a Discord moderation bot
that serves a Call of Duty competitive (CDL Ranked) community.

CONTEXT - The rule under examination:
- source_id: {rule_id}
- title: {rule['title']}
- severity_default: {rule['severity_default']}
- description: {rule['description']}

CATEGORY for this batch: {category}
- clear_violation: an unambiguous violation of the rule.
- near_miss: borderline content that a junior mod might flag but senior mods would not.
- false_positive_bait: content that LOOKS like a violation due to keywords/jargon but
  is actually benign (e.g., gaming slang like "free", "uninstall", "dog water").
- gaming_vernacular: competitive-FPS register that uses provocative-sounding language
  but is normal trash talk between peers.
- ambiguous: genuinely uncertain - reasonable mods could disagree.
- benign: clearly fine; useful as a question-about-the-rule (informational citation)
  or as content that has nothing to do with this rule.

EXAMPLES from our hand-authored anchor set (DO NOT copy these verbatim):
{examples_block}

TASK: Produce exactly {CASES_PER_CELL} new realistic Discord messages for this
(rule x category) cell. Each must be:
1. Plausible content from a CDL Ranked Discord member (FPS / COD register, casual
   typing, lowercase OK, gaming slang OK).
2. Distinct from the example messages in topic and phrasing.
3. Labeled with the appropriate fields.

Use these field rules:
- expected_violation_type MUST be one of:
  spam, harassment, hate_speech, toxic_attack, self_promo, spoiler, flooding, no_violation
- For benign-question-about-a-rule cases, set expected_violation_type=no_violation
  AND expected_rule_match to the relevant rule (informational citation).
- expected_severity MUST be one of: low, medium, high, critical
- expected_rule_match MUST be either "{rule_id}" or null. Use null only when the
  message has nothing to do with the rule (typical for benign category cases that
  aren't questions about the rule).
- expected_suggested_action MUST be one of:
  no_action, warn, remove_message, timeout_or_mute_recommendation, escalate_to_human
- channel_context: a plausible channel name (e.g., general, competitive, content-share,
  ranked-lfg, tournament-info, memes).

OUTPUT FORMAT - Return ONLY a JSON array of {CASES_PER_CELL} objects, no prose,
no markdown fences. Each object has the keys:
  content, expected_violation_type, expected_severity, expected_rule_match,
  category, expected_suggested_action, notes, channel_context

Set ``category`` to exactly: "{category}"
Keep ``notes`` to one sentence explaining why the label is correct.
"""


def call_anthropic(prompt: str) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit(
            "anthropic SDK not installed. Run `pip install anthropic` or use --dry-run."
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set in environment.")

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = []
    for block in resp.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


def parse_response(raw: str) -> list[dict[str, Any]]:
    """Parse the model's JSON array out of its response, tolerating fences."""
    text = raw.strip()
    # Strip a single fenced block if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract the largest JSON array substring as a fallback.
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    return [d for d in data if isinstance(d, dict)]


def next_case_id_start(anchors: list[dict[str, Any]]) -> int:
    """Find the next case_id integer to use for proposals."""
    max_n = 0
    pattern = re.compile(r"^eval_(\d+)$")
    for a in anchors:
        m = pattern.match(a.get("case_id", ""))
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print prompts only, do not call the API.",
    )
    p.add_argument(
        "--rules",
        type=str,
        default=None,
        help="Comma-separated subset of rule ids to generate for (e.g. rule_006,rule_008).",
    )
    p.add_argument(
        "--out",
        type=str,
        default=str(OUT_CSV),
        help=f"CSV output path (default: {OUT_CSV}).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    rules = load_rules()
    anchors = load_anchors()

    rule_filter: set[str] | None = None
    if args.rules:
        rule_filter = {r.strip() for r in args.rules.split(",") if r.strip()}

    next_id = next_case_id_start(anchors)
    proposals: list[dict[str, Any]] = []
    cells_run = 0
    cells_skipped = 0

    for rule in rules:
        rule_id = rule["source_id"]
        if rule_filter and rule_id not in rule_filter:
            continue
        categories = DEFAULT_CATEGORIES_PER_RULE.get(rule_id, [])
        for category in categories:
            examples = pick_anchor_examples(anchors, rule_id, category)
            if not examples:
                cells_skipped += 1
                print(f"[skip] {rule_id} / {category}: no anchor examples available.")
                continue

            prompt = build_prompt(rule, category, examples)
            cells_run += 1

            if args.dry_run:
                print("=" * 78)
                print(f"PROMPT for {rule_id} / {category}")
                print("=" * 78)
                print(prompt)
                continue

            print(f"[call] {rule_id} / {category}")
            try:
                raw = call_anthropic(prompt)
            except Exception as exc:  # pragma: no cover - one-off script
                print(f"  -> API error: {exc!r}")
                continue

            parsed = parse_response(raw)
            if not parsed:
                print(f"  -> could not parse response; skipping cell.")
                continue

            for item in parsed[:CASES_PER_CELL]:
                proposals.append(
                    {
                        "proposed_case_id": f"eval_{next_id:03d}",
                        "content": item.get("content", ""),
                        "proposed_violation_type": item.get("expected_violation_type", ""),
                        "proposed_severity": item.get("expected_severity", ""),
                        "proposed_rule_match": item.get("expected_rule_match") or "",
                        "proposed_suggested_action": item.get(
                            "expected_suggested_action", ""
                        ),
                        "category": item.get("category", category),
                        "notes": item.get("notes", ""),
                        "channel_context": item.get("channel_context", ""),
                        "reviewer_decision": "",
                        "reviewer_edits": "",
                    }
                )
                next_id += 1

    if args.dry_run:
        print(f"\n[dry-run] {cells_run} cells would be called, {cells_skipped} skipped.")
        print(f"[dry-run] Estimated proposals: {cells_run * CASES_PER_CELL}.")
        return 0

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(proposals)

    print()
    print(f"Wrote {len(proposals)} proposals to {out_path}")
    print(f"Cells called: {cells_run}, skipped: {cells_skipped}")
    print()
    print("NEXT STEPS:")
    print(f"  1. Open {out_path} in a spreadsheet or editor.")
    print("  2. For each row set reviewer_decision to: approved | rejected | edited")
    print('     - For "edited" rows, put a JSON object in reviewer_edits with overrides,')
    print('       e.g. {"expected_severity": "medium", "category": "near_miss"}.')
    print("  3. Reject any case that takes >10s to confidently label.")
    print("  4. Save the CSV.")
    print("  5. Run: python scripts/merge_reviewed_cases.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
