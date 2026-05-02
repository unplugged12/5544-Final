"""Dataset loader for the moderation behavior eval cases.

The eval JSON lives at ``data/eval/eval_moderation.json`` (excluded from the
``data/ingest.py`` glob so it never enters Chroma). Layouts:

- Local dev:  ``<repo>/backend/tests/eval/dataset.py`` + ``<repo>/data/eval/eval_moderation.json`` (4 up)
- Docker:     ``/app/tests/eval/dataset.py`` + ``/app/data/eval/eval_moderation.json`` (3 up)

We mirror the multi-candidate path resolution from ``services/utils.py:_load_valid_rule_labels``
so the harness works in both layouts even though it's only expected to run locally.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


_DEFAULT_FILENAME = "eval_moderation.json"


@dataclass(frozen=True)
class EvalCase:
    """One labeled moderation eval case.

    Mirrors the schema in ``data/eval/eval_moderation.json``. ``channel_context``
    is optional in the schema; default to ``None`` when absent.
    """

    case_id: str
    content: str
    expected_violation_type: str
    expected_severity: str
    expected_rule_match: str | None
    category: str
    expected_suggested_action: str
    notes: str
    channel_context: str | None = None


def _candidate_paths() -> list[Path]:
    here = Path(__file__).resolve()
    # Local: backend/tests/eval/dataset.py -> repo root is 4 up
    # Docker: /app/tests/eval/dataset.py -> /app is 3 up; data is a bind mount under /app
    return [
        here.parent.parent.parent.parent / "data" / "eval" / _DEFAULT_FILENAME,
        here.parent.parent.parent / "data" / "eval" / _DEFAULT_FILENAME,
    ]


def _resolve_default_path() -> Path:
    for cand in _candidate_paths():
        if cand.is_file():
            return cand
    # Return the first candidate so error messages point at the expected local path
    return _candidate_paths()[0]


def load_cases(path: Path | None = None) -> list[EvalCase]:
    """Load all eval cases from the JSON dataset.

    Pass an explicit ``path`` for tests; otherwise resolves relative to this
    file using the same multi-candidate trick as ``services/utils.py``.
    """
    target = Path(path) if path is not None else _resolve_default_path()
    with target.open("r", encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get("eval_moderation", [])
    cases: list[EvalCase] = []
    for entry in raw:
        cases.append(
            EvalCase(
                case_id=entry["case_id"],
                content=entry["content"],
                expected_violation_type=entry["expected_violation_type"],
                expected_severity=entry["expected_severity"],
                expected_rule_match=entry.get("expected_rule_match"),
                category=entry["category"],
                expected_suggested_action=entry["expected_suggested_action"],
                notes=entry.get("notes", ""),
                channel_context=entry.get("channel_context"),
            )
        )
    return cases
