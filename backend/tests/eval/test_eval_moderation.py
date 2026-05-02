"""Real-LLM behavior eval over the labeled moderation dataset.

This module is opt-in: every test is marked ``@pytest.mark.eval`` and the
default ``addopts = -m "not eval"`` in ``pytest.ini`` excludes it from the
normal ``pytest tests/`` run. CI runs it via the nightly workflow with
``ANTHROPIC_API_KEY`` set.

Implementation notes:

- Calls the real ``moderation_service._run_moderation_llm`` (not a mock). The
  fixtures in ``tests/conftest.py`` are NOT autouse, so importing this module
  does not patch out the LLM provider — we get real calls automatically.
- ``EVAL_SHOTS`` env var (default ``1``) controls how many times each case is
  classified. For shots > 1 we majority-vote ``violation_type``/``matched_rule``
  and median-vote ``severity`` (rank ordering: low<medium<high<critical).
- Per-case results are written to ``backend/eval/artifacts/eval-<ts>.json``
  with a ``latest.json`` pointer at session end via a session-scoped fixture.
- Result cache: ``backend/eval/.cache/<sha256>.json`` keyed by
  ``content + system_prompt + model + shot_index`` so unchanged cases skip the
  API call when re-run. Cache busts automatically when the prompt changes.
- ``category=ambiguous`` cases are marked ``xfail`` since they're inherently
  uncertain — we still record the prediction for debugging.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import os
import shutil
from pathlib import Path

import pytest

from eval._runner import aggregate as _aggregate
from eval._runner import classify_one as _classify_one
from tests.eval.dataset import EvalCase, load_cases


# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
# backend/tests/eval/test_eval_moderation.py -> backend/ is 2 up
_BACKEND_DIR = _HERE.parent.parent.parent
_ARTIFACT_DIR = _BACKEND_DIR / "eval" / "artifacts"
_CACHE_DIR = _BACKEND_DIR / "eval" / ".cache"
_DATASET_PATH = _BACKEND_DIR.parent / "data" / "eval" / "eval_moderation.json"


def _shots() -> int:
    raw = os.getenv("EVAL_SHOTS", "1")
    try:
        n = int(raw)
    except ValueError:
        n = 1
    return max(1, n)


def _cache_dir() -> Path:
    override = os.getenv("EVAL_CACHE_DIR")
    return Path(override) if override else _CACHE_DIR


def _use_cache() -> bool:
    return os.getenv("EVAL_NO_CACHE", "").lower() not in {"1", "true", "yes"}


# ---------------------------------------------------------------------------
# Module-scoped collector — populated as tests run, written by session finaliser
# ---------------------------------------------------------------------------

_RESULTS: list[dict] = []


# ---------------------------------------------------------------------------
# Parametrize over all loaded cases
# ---------------------------------------------------------------------------

def _all_cases() -> list[EvalCase]:
    try:
        return load_cases()
    except (FileNotFoundError, OSError):
        return []


def _case_id(case: EvalCase) -> str:
    return case.case_id


_CASES = _all_cases()


@pytest.mark.eval
@pytest.mark.parametrize("case", _CASES, ids=[_case_id(c) for c in _CASES])
def test_moderation_eval_case(case: EvalCase) -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set; eval requires real LLM access")
    # Make the missing-dataset case a clear skip rather than the silent
    # "no tests collected" outcome you get from an empty parametrize list.
    if not _CASES and not _DATASET_PATH.is_file():
        pytest.skip(f"eval dataset missing at {_DATASET_PATH}")

    # Cases tagged ambiguous are inherently uncertain — record the prediction
    # but don't fail the suite if the model picks the other side.
    if case.category == "ambiguous":
        pytest.xfail("ambiguous case; recording prediction without strict assertion")

    shots_n = _shots()
    cache_dir = _cache_dir()
    use_cache = _use_cache()

    async def _runner() -> list[dict]:
        return [
            await _classify_one(
                case.content, i, use_cache=use_cache, cache_dir=cache_dir
            )
            for i in range(shots_n)
        ]

    raw_shots = asyncio.run(_runner())
    aggregate = _aggregate(raw_shots)

    record = {
        "case_id": case.case_id,
        "content": case.content,
        "category": case.category,
        "channel_context": case.channel_context,
        "expected": {
            "violation_type": case.expected_violation_type,
            "rule_match": case.expected_rule_match,
            "severity": case.expected_severity,
            "suggested_action": case.expected_suggested_action,
        },
        "predicted": {
            "violation_type": aggregate["violation_type"],
            "matched_rule": aggregate.get("matched_rule"),
            "severity": aggregate["severity"],
            "suggested_action": aggregate["suggested_action"],
            "confidence_note": aggregate.get("confidence_note", ""),
        },
        "shots": shots_n,
        "raw_shots": raw_shots,
    }
    _RESULTS.append(record)

    assert aggregate["violation_type"] == case.expected_violation_type, (
        f"{case.case_id}: predicted violation_type "
        f"{aggregate['violation_type']!r} != expected {case.expected_violation_type!r}"
    )


# ---------------------------------------------------------------------------
# Session finaliser — write artifact + latest.json on collected sessions only
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _eval_artifact_writer():
    """Write the per-session JSON artifact at teardown if any eval cases ran."""
    yield
    if not _RESULTS:
        return

    _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    artifact_path = _ARTIFACT_DIR / f"eval-{ts}.json"
    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "shots": _shots(),
        "case_count": len(_RESULTS),
        "results": _RESULTS,
    }
    try:
        with artifact_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except OSError:
        return

    # Maintain a stable ``latest.json`` next to the timestamped file. We copy
    # rather than symlink so Windows works without admin/Developer Mode.
    latest_path = _ARTIFACT_DIR / "latest.json"
    try:
        shutil.copyfile(artifact_path, latest_path)
    except OSError:
        pass
