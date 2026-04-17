"""Shared utilities for service modules."""

import json
import re

from models.schemas import Citation


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


def build_citations_and_rule(
    chunks: list[dict],
) -> tuple[list[Citation], str | None, list[str]]:
    """Build Citation objects, pick the first rule-type label, and collect source IDs."""
    citations = [
        Citation(
            source_id=c["source_id"],
            citation_label=c["citation_label"],
            snippet=c["content"][:150],
        )
        for c in chunks
    ]
    matched_rule = next(
        (c["citation_label"] for c in chunks if c.get("source_type") == "rule"),
        None,
    )
    raw_source_ids = [c["source_id"] for c in chunks]
    return citations, matched_rule, raw_source_ids
