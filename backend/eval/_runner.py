"""Shared eval-runner primitives used by both ``backend.eval.__main__`` (CLI)
and ``tests/eval/test_eval_moderation.py`` (pytest harness).

Keeping cache-key, classify, and aggregate logic in one place prevents the two
call sites from drifting on the next bug fix.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_RANK_SEVERITY = {v: k for k, v in _SEVERITY_RANK.items()}


def cache_key(content: str, system_prompt: str, model: str, shot_index: int) -> str:
    """SHA-256 cache key. Bursts naturally when prompt or model version change."""
    h = hashlib.sha256()
    h.update(content.encode("utf-8"))
    h.update(b"\x00")
    h.update(system_prompt.encode("utf-8"))
    h.update(b"\x00")
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(str(shot_index).encode("utf-8"))
    return h.hexdigest()


def read_cache(cache_dir: Path, key: str) -> dict | None:
    path = cache_dir / f"{key}.json"
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_cache(cache_dir: Path, key: str, payload: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.json"
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError:
        pass


async def classify_one(
    content: str,
    shot_index: int,
    *,
    use_cache: bool,
    cache_dir: Path,
) -> dict:
    """Run one moderation classification (real LLM) — uses cache if available.

    Imports are lazy so this module can be loaded by pytest collection without
    pulling in chromadb / SentenceTransformer. Callers MUST set sys.path so
    ``backend/`` is importable; ``__main__`` and the pytest harness both do.
    """
    from config import settings  # noqa: PLC0415
    from prompts.moderation_prompt import get_system_prompt  # noqa: PLC0415
    from services import moderation_service  # noqa: PLC0415

    system_prompt = get_system_prompt()
    model = settings.ANTHROPIC_MODEL or settings.OPENAI_MODEL or "unknown"
    key = cache_key(content, system_prompt, model, shot_index)

    if use_cache:
        cached = read_cache(cache_dir, key)
        if cached is not None:
            cached["_cache_hit"] = True
            return cached

    result = await moderation_service._run_moderation_llm(content)
    payload = {
        "violation_type": result.violation_type.value,
        "matched_rule": result.matched_rule,
        "severity": result.severity.value,
        "suggested_action": result.suggested_action.value,
        "confidence_note": result.confidence_note,
        "explanation": result.explanation,
        "provider_name": result.provider_name,
        "_cache_hit": False,
    }
    if use_cache:
        write_cache(cache_dir, key, payload)
    return payload


def aggregate(shots: list[dict]) -> dict:
    """Majority-vote ``violation_type`` / ``matched_rule`` / ``suggested_action``;
    upper-median (rounds up on even N) on ``severity``.

    The severity vote uses ``ranks[len(ranks) // 2]`` which is the upper of the
    two middle elements when N is even (n=2 -> index 1, n=4 -> index 2). This
    is intentional: erring high on severity favours surfacing borderline cases
    for human review over silently downgrading.
    """
    if len(shots) == 1:
        return shots[0]

    vt = Counter(s["violation_type"] for s in shots).most_common(1)[0][0]
    matched_rule = Counter(s.get("matched_rule") for s in shots).most_common(1)[0][0]
    sa = Counter(s["suggested_action"] for s in shots).most_common(1)[0][0]

    ranks = sorted(_SEVERITY_RANK.get(s["severity"], 0) for s in shots)
    severity = _RANK_SEVERITY[ranks[len(ranks) // 2]]

    return {
        "violation_type": vt,
        "matched_rule": matched_rule,
        "severity": severity,
        "suggested_action": sa,
        "confidence_note": shots[0].get("confidence_note", ""),
        "explanation": shots[0].get("explanation", ""),
        "provider_name": shots[0].get("provider_name", ""),
        "_per_shot": shots,
    }
