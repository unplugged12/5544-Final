"""Shared utilities for service modules."""

import json
import logging
import re
from pathlib import Path

from models.schemas import Citation

logger = logging.getLogger(__name__)


def _rules_json_candidates() -> list[Path]:
    """Path candidates for ``data/seed/rules.json`` across local + Docker layouts.

    Local: ``<repo>/backend/services/utils.py`` + ``<repo>/data/seed/rules.json`` (3 up).
    Docker: ``/app/services/utils.py`` + ``/app/data/seed/rules.json`` (2 up;
    ``data`` is a bind mount under ``/app``).
    """
    here = Path(__file__).resolve()
    return [
        here.parent.parent.parent / "data" / "seed" / "rules.json",
        here.parent.parent / "data" / "seed" / "rules.json",
    ]


def _load_rules_json() -> dict:
    """Read ``rules.json`` from the first existing candidate path.

    Returns the parsed JSON dict, or an empty ``{"rules": []}`` if no candidate
    is readable. Failures are logged at WARNING — silent fallback was the
    Docker-path bug that disabled matched_rule validation in production, so
    callers that depend on a non-empty result should assert at startup.
    """
    rules_path = next((p for p in _rules_json_candidates() if p.is_file()), None)
    if rules_path is None:
        logger.warning(
            "rules.json not found in any candidate path: %s",
            [str(p) for p in _rules_json_candidates()],
        )
        return {"rules": []}
    try:
        with rules_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Could not parse rules.json at %s: %s", rules_path, exc)
        return {"rules": []}


def _load_valid_rule_labels() -> set[str]:
    """Canonical rule identifiers (citation_label, title, source_id), loaded once."""
    labels: set[str] = set()
    for rule in _load_rules_json().get("rules", []):
        for key in ("citation_label", "title", "source_id"):
            value = rule.get(key)
            if value:
                labels.add(value)
    return labels


def _load_rule_reference_list() -> str:
    """Markdown bullet list of every rule's ``citation_label``, loaded once.

    Used by mod_draft_prompt to give the LLM the full rule taxonomy so it can
    cite the correct rule even when retrieval surfaces an irrelevant one.
    Built from rules.json so a future rename can't silently drift the prompt.
    """
    lines: list[str] = []
    for rule in _load_rules_json().get("rules", []):
        label = rule.get("citation_label") or rule.get("title", "")
        if label:
            lines.append(f"- {label}")
    return "\n".join(lines)


def _load_rule_label_to_source_id() -> dict[str, str]:
    """Map every known rule reference (citation_label, title, source_id) to its
    canonical ``source_id``. Used by the eval metrics path to normalise
    predicted labels (LLM emits ``"Rule 6: Stay On Topic"``) and expected
    labels (dataset stores ``"rule_006"``) before comparing.
    """
    out: dict[str, str] = {}
    for rule in _load_rules_json().get("rules", []):
        sid = rule.get("source_id")
        if not sid:
            continue
        out[sid] = sid
        for key in ("citation_label", "title"):
            value = rule.get(key)
            if value:
                out[value] = sid
    return out


VALID_RULE_LABELS: set[str] = _load_valid_rule_labels()
RULE_REFERENCE_LIST: str = _load_rule_reference_list()
RULE_LABEL_TO_SOURCE_ID: dict[str, str] = _load_rule_label_to_source_id()
logger.info(
    "moderation.rules_loaded: %d valid rule labels, %d reference lines, %d label aliases",
    len(VALID_RULE_LABELS),
    RULE_REFERENCE_LIST.count("\n") + 1 if RULE_REFERENCE_LIST else 0,
    len(RULE_LABEL_TO_SOURCE_ID),
)


def canonical_rule_id(label: str | None) -> str | None:
    """Return the canonical ``source_id`` for any rule reference, or ``None``.

    Passes through unknown strings unchanged so confusion matrices preserve
    visible information about hallucinated rule labels (rather than silently
    collapsing them to None — that case is already handled upstream by the
    matched_rule validator in moderation_service).
    """
    if not label:
        return None
    return RULE_LABEL_TO_SOURCE_ID.get(label, label)


_CONFIDENCE_TIER_PATTERN = re.compile(r"\s*(high|moderate|low)\b", re.IGNORECASE)


def parse_confidence_tier(text: str | None) -> str | None:
    """Return ``'high'|'moderate'|'low'`` from a confidence_note string, or None.

    Accepts both raw tier-prefixed text (``"Low - uncertain"``) and the legacy
    free-text trailer format (``"Confidence: Low - reason"``). Tier match is
    anchored at the start so a stray "low" later in a reason doesn't trigger.
    """
    if not text:
        return None
    body = text.strip()
    if body.lower().startswith("confidence:"):
        body = body.split(":", 1)[1].strip()
    match = _CONFIDENCE_TIER_PATTERN.match(body)
    return match.group(1).lower() if match else None


def extract_confidence(text: str) -> tuple[str, str | None]:
    """Split the trailing 'Confidence: ...' note from the body text."""
    match = re.search(
        r"\n?Confidence:\s*(High|Moderate|Low)\s*[-\u2014]\s*(.+)",
        text,
        re.IGNORECASE,
    )
    if match:
        body = text[: match.start()].strip()
        confidence_note = match.group(0).strip()
        return body, confidence_note
    return text.strip(), None


def parse_json_response(text: str) -> dict:
    """Strip markdown fences from an LLM reply and parse the JSON body."""
    cleaned = (
        text.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    return json.loads(cleaned)


_BRACKET_RULE_PATTERN = re.compile(r"\[Rule \d+:[^\]]+\]")
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _extract_bracket_rule_label(body: str) -> str | None:
    """Pull the first [Rule N: Title] citation out of a drafted body, if any."""
    match = _BRACKET_RULE_PATTERN.search(body)
    if not match:
        return None
    return match.group(0).strip("[]")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(text.lower()))


def build_citations_and_rule(
    chunks: list[dict],
    drafted_body: str = "",
    score_threshold: float | None = None,
) -> tuple[list[Citation], str | None, list[str]]:
    """Build Citation objects, pick the most-relevant rule label, collect source IDs.

    Selection order for matched_rule:
      1. Bracket-extracted [Rule N: ...] label from drafted_body that matches a
         retrieved rule chunk's citation_label or title.
      2. Rule chunk with highest token-overlap against drafted_body.
      3. None.

    Rule chunks whose distance exceeds score_threshold are filtered out before
    selection (the prior implementation picked rank-1 blindly, which surfaced
    Rule 8 for "Medal of Honor" via lexical "trading/talking" overlap).
    """
    rule_chunks = [c for c in chunks if c.get("source_type") == "rule"]
    if score_threshold is not None:
        rule_chunks = [
            c for c in rule_chunks if c.get("distance", 1.0) <= score_threshold
        ]

    matched_rule: str | None = None

    bracket_label = _extract_bracket_rule_label(drafted_body)
    if bracket_label:
        # Strict match: prefer a retrieved chunk whose citation_label or title
        # exactly matches the bracket. Avoid loose endswith matches — those
        # can collide e.g. "Rule 99: Stay On Topic" (hallucinated) vs a chunk
        # titled "Stay On Topic". Validate against the canonical rule label
        # set as the final fallback for cases where the LLM cited a real rule
        # that retrieval didn't surface.
        bracket_title = bracket_label.split(":", 1)[1].strip() if ":" in bracket_label else ""
        for c in rule_chunks:
            if (
                c.get("citation_label") == bracket_label
                or c.get("title") == bracket_label
                or (bracket_title and c.get("title") == bracket_title)
            ):
                matched_rule = c["citation_label"]
                break
        if matched_rule is None and bracket_label in VALID_RULE_LABELS:
            matched_rule = bracket_label

    if matched_rule is None and rule_chunks and drafted_body:
        body_tokens = _tokens(drafted_body)
        if body_tokens:
            best_score = -1
            best_label: str | None = None
            for c in rule_chunks:
                chunk_tokens = _tokens(
                    f"{c.get('citation_label', '')} {c.get('title', '')} {c.get('content', '')}"
                )
                overlap = len(body_tokens & chunk_tokens)
                if overlap > best_score:
                    best_score = overlap
                    best_label = c["citation_label"]
            if best_score > 0:
                matched_rule = best_label

    citations = [
        Citation(
            source_id=c["source_id"],
            citation_label=c["citation_label"],
            snippet=c["content"][:150],
        )
        for c in chunks
    ]
    raw_source_ids = [c["source_id"] for c in chunks]
    return citations, matched_rule, raw_source_ids
