"""Shared utilities for service modules."""

import re


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
