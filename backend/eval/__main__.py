"""CLI entrypoint for the moderation behavior eval.

Usage (run from the ``backend/`` directory):
    python -m eval [--dataset PATH] [--shots N] [--out PATH]
                   [--filter rule=rule_006] [--cache-dir PATH] [--no-cache]

Reuses the same classification path as ``tests/eval/test_eval_moderation.py``
(``moderation_service._run_moderation_llm``) and the same dataset loader.
Computes per-rule precision/recall, false-positive rate on benign cases, and
prints a 19x19 confusion matrix (18 rules + null) as a Markdown summary to
stdout. Always exits 0 so calling code can gate on the JSON artifact.

The CLI is invoked from ``backend/`` rather than the repo root so that
``backend/`` itself is on sys.path the same way it is for pytest and uvicorn.
A package-marker ``backend/__init__.py`` would change pytest's rootdir
detection and break CI imports — see commit history.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

# Make ``backend`` importable when run as ``python -m backend.eval`` from repo root
_HERE = Path(__file__).resolve()
_BACKEND_DIR = _HERE.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from eval._runner import aggregate as _aggregate  # noqa: E402
from eval._runner import classify_one as _classify_one  # noqa: E402
from services.utils import canonical_rule_id  # noqa: E402

_DEFAULT_DATASET = (
    _BACKEND_DIR.parent / "data" / "eval" / "eval_moderation.json"
)
_DEFAULT_ARTIFACT_DIR = _BACKEND_DIR / "eval" / "artifacts"
_DEFAULT_CACHE_DIR = _BACKEND_DIR / "eval" / ".cache"


# ---------------------------------------------------------------------------
# Filter parsing — accepts ``rule=rule_006,category=benign`` (multiple pairs)
# ---------------------------------------------------------------------------

def _parse_filter(spec: str | None) -> dict[str, str]:
    """Parse ``key=value`` pairs separated by commas into a dict.

    Examples: ``"rule=rule_006"`` -> ``{"rule": "rule_006"}``;
    ``"rule=rule_006,category=benign"`` -> two-key dict.
    """
    if not spec:
        return {}
    out: dict[str, str] = {}
    for piece in spec.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if "=" not in piece:
            raise SystemExit(f"--filter must be 'key=value' pairs (got {piece!r})")
        key, _, value = piece.partition("=")
        out[key.strip()] = value.strip()
    return out


def _case_matches(case: dict, filt: dict[str, str]) -> bool:
    for key, value in filt.items():
        if key in {"rule", "expected_rule_match"}:
            if case.get("expected_rule_match") != value:
                return False
        elif key == "category":
            if case.get("category") != value:
                return False
        elif key in {"violation", "expected_violation_type"}:
            if case.get("expected_violation_type") != value:
                return False
        else:
            # Generic field match
            if str(case.get(key)) != value:
                return False
    return True


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _expected_rule(record: dict) -> str | None:
    return canonical_rule_id(record["expected"]["rule_match"])


def _predicted_rule(record: dict) -> str | None:
    return canonical_rule_id(record["predicted"]["matched_rule"])


def _per_rule_pr(records: list[dict]) -> dict[str, dict[str, float]]:
    """Compute precision/recall per canonical rule id (``rule_NNN``).

    Both ``expected.rule_match`` (canonical IDs in the dataset) and
    ``predicted.matched_rule`` (LLM emits citation labels like
    ``"Rule 6: Stay On Topic"``) are normalised through ``canonical_rule_id``
    before comparison so the metrics aren't systematically wrong.
    """
    rule_keys = sorted(
        {_expected_rule(r) for r in records if _expected_rule(r)}
        | {_predicted_rule(r) for r in records if _predicted_rule(r)}
    )
    out: dict[str, dict[str, float]] = {}
    for rk in rule_keys:
        tp = sum(
            1 for r in records
            if _expected_rule(r) == rk and _predicted_rule(r) == rk
        )
        fp = sum(
            1 for r in records
            if _predicted_rule(r) == rk and _expected_rule(r) != rk
        )
        fn = sum(
            1 for r in records
            if _expected_rule(r) == rk and _predicted_rule(r) != rk
        )
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        out[rk] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
        }
    return out


def _fpr_on_benign(records: list[dict]) -> dict[str, float]:
    benign = [r for r in records if r["expected"]["violation_type"] == "no_violation"]
    if not benign:
        return {"benign_total": 0, "false_positives": 0, "fpr": 0.0}
    fps = sum(1 for r in benign if r["predicted"]["violation_type"] != "no_violation")
    return {
        "benign_total": len(benign),
        "false_positives": fps,
        "fpr": round(fps / len(benign), 3),
    }


def _confusion_matrix(records: list[dict]) -> dict[str, dict[str, int]]:
    """Confusion matrix keyed by canonical expected rule id -> predicted rule id.

    Null is rendered as ``"<null>"``. Both axes go through ``canonical_rule_id``
    so a predicted ``"Rule 6: Stay On Topic"`` matches an expected ``"rule_006"``.
    """
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in records:
        exp = _expected_rule(r) or "<null>"
        pred = _predicted_rule(r) or "<null>"
        matrix[exp][pred] += 1
    return {k: dict(v) for k, v in matrix.items()}


# ---------------------------------------------------------------------------
# Markdown summary
# ---------------------------------------------------------------------------

def _format_markdown(summary: dict) -> str:
    lines: list[str] = []
    lines.append(f"# ModBot Eval Summary")
    lines.append("")
    lines.append(f"- Generated: {summary['generated_at']}")
    lines.append(f"- Cases: {summary['case_count']}")
    lines.append(f"- Shots per case: {summary['shots']}")
    fpr = summary["fpr_on_benign"]
    lines.append(
        f"- Benign FPR: {fpr['fpr']} ({fpr['false_positives']}/{fpr['benign_total']})"
    )
    lines.append("")
    lines.append("## Per-rule precision / recall")
    lines.append("")
    lines.append("| Rule | TP | FP | FN | Precision | Recall |")
    lines.append("|------|---:|---:|---:|----------:|-------:|")
    for rk, m in sorted(summary["per_rule"].items()):
        lines.append(
            f"| {rk} | {m['tp']} | {m['fp']} | {m['fn']} "
            f"| {m['precision']} | {m['recall']} |"
        )
    lines.append("")
    lines.append("## Confusion matrix (expected -> predicted)")
    lines.append("")
    lines.append("| expected \\ predicted | count | top-prediction |")
    lines.append("|------|---:|------|")
    for exp, row in sorted(summary["confusion_matrix"].items()):
        total = sum(row.values())
        if not row:
            continue
        top_pred, top_count = max(row.items(), key=lambda kv: kv[1])
        lines.append(f"| {exp} | {total} | {top_pred} ({top_count}) |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval",
        description=(
            "Run the ModBot moderation behavior eval over a labeled dataset. "
            "Calls the real LLM via moderation_service._run_moderation_llm — "
            "requires ANTHROPIC_API_KEY (or the configured primary provider's key). "
            "Run from the backend/ directory."
        ),
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=_DEFAULT_DATASET,
        help=f"Path to the eval JSON (default: {_DEFAULT_DATASET}).",
    )
    parser.add_argument(
        "--shots",
        type=int,
        default=1,
        help="Number of LLM shots per case; majority-vote for >1 (default: 1).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Path to write the JSON artifact "
            f"(default: {_DEFAULT_ARTIFACT_DIR}/eval-<ts>.json)."
        ),
    )
    parser.add_argument(
        "--filter",
        dest="filter_spec",
        default=None,
        help=(
            "Filter cases by predicate(s); comma-separate multiple pairs, "
            "e.g. 'rule=rule_006' or 'rule=rule_006,category=benign'."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=_DEFAULT_CACHE_DIR,
        help=f"Result cache directory (default: {_DEFAULT_CACHE_DIR}).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass the result cache (always call the LLM).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Lazy imports so --help doesn't pull in chromadb etc.
    from tests.eval.dataset import load_cases

    filt = _parse_filter(args.filter_spec)

    try:
        cases = load_cases(args.dataset)
    except FileNotFoundError as exc:
        print(f"ERROR: dataset not found: {exc}", file=sys.stderr)
        return 0

    selected: list[dict] = []
    for case in cases:
        case_dict = {
            "case_id": case.case_id,
            "content": case.content,
            "expected_violation_type": case.expected_violation_type,
            "expected_severity": case.expected_severity,
            "expected_rule_match": case.expected_rule_match,
            "category": case.category,
            "expected_suggested_action": case.expected_suggested_action,
            "channel_context": case.channel_context,
        }
        if _case_matches(case_dict, filt):
            selected.append(case_dict)

    if not selected:
        print("No cases matched the filter.", file=sys.stderr)
        # Still emit an empty artifact for downstream scripts.

    use_cache = not args.no_cache
    cache_dir = Path(args.cache_dir)
    shots_n = max(1, int(args.shots))

    async def _runner() -> list[dict]:
        records: list[dict] = []
        for case in selected:
            shots = [
                await _classify_one(
                    case["content"], i, use_cache=use_cache, cache_dir=cache_dir
                )
                for i in range(shots_n)
            ]
            agg = _aggregate(shots)
            records.append({
                "case_id": case["case_id"],
                "content": case["content"],
                "category": case["category"],
                "channel_context": case.get("channel_context"),
                "expected": {
                    "violation_type": case["expected_violation_type"],
                    "rule_match": case["expected_rule_match"],
                    "severity": case["expected_severity"],
                    "suggested_action": case["expected_suggested_action"],
                },
                "predicted": {
                    "violation_type": agg["violation_type"],
                    "matched_rule": agg.get("matched_rule"),
                    "severity": agg["severity"],
                    "suggested_action": agg["suggested_action"],
                    "confidence_note": agg.get("confidence_note", ""),
                },
                "shots": shots_n,
                "raw_shots": shots,
            })
        return records

    records = asyncio.run(_runner())

    summary = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "shots": shots_n,
        "case_count": len(records),
        "filter": filt,
        "per_rule": _per_rule_pr(records),
        "fpr_on_benign": _fpr_on_benign(records),
        "confusion_matrix": _confusion_matrix(records),
        "results": records,
    }

    # Resolve artifact path
    if args.out is None:
        _DEFAULT_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        out_path = _DEFAULT_ARTIFACT_DIR / f"eval-{ts}.json"
    else:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Maintain latest.json next to the timestamped file (copy, not symlink, for Windows)
    latest_path = out_path.parent / "latest.json"
    try:
        shutil.copyfile(out_path, latest_path)
    except OSError:
        pass

    print(_format_markdown(summary))
    print()
    print(f"Artifact: {out_path}")
    print(f"Latest:   {latest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
