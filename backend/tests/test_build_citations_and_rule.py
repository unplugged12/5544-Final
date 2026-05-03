"""Unit tests for build_citations_and_rule's three-tier matched_rule selection.

(a) bracket-extract from drafted_body wins when label is in surviving chunks
(b) token-overlap fallback when no bracket present
(c) None when all rule chunks are filtered out by score_threshold
"""

from __future__ import annotations

from services.utils import build_citations_and_rule


def _chunk(
    *,
    source_id: str,
    citation_label: str,
    title: str,
    content: str,
    distance: float = 0.2,
    source_type: str = "rule",
) -> dict:
    return {
        "source_id": source_id,
        "citation_label": citation_label,
        "title": title,
        "content": content,
        "source_type": source_type,
        "distance": distance,
    }


def test_bracket_extraction_wins_when_label_in_chunks():
    """If drafted_body contains [Rule N: Title] and a chunk has that label,
    the bracket label is returned even if a different chunk would have higher
    token-overlap."""
    chunks = [
        _chunk(
            source_id="rule_001",
            citation_label="Rule 1: No Harassment or Bullying",
            title="No Harassment or Bullying",
            content="Do not harass other members. " * 10,  # high token-overlap with body
            distance=0.2,
        ),
        _chunk(
            source_id="rule_006",
            citation_label="Rule 6: Stay On Topic",
            title="Stay On Topic",
            content="Use channels for designated purpose.",
            distance=0.5,
        ),
    ]
    body = (
        "Please keep gameplay discussion in the right channel. "
        "[Rule 6: Stay On Topic]. "
        "Do not harass other members of the community."
    )

    _, matched_rule, _ = build_citations_and_rule(
        chunks, drafted_body=body, score_threshold=0.65
    )

    assert matched_rule == "Rule 6: Stay On Topic"


def test_token_overlap_fallback_picks_best_chunk():
    """No bracket in body — pick the rule chunk with highest token overlap."""
    chunks = [
        _chunk(
            source_id="rule_004",
            citation_label="Rule 4: No Unauthorized Self-Promotion",
            title="No Unauthorized Self-Promotion",
            content="Posting Twitch YouTube social media links only in content-share.",
            distance=0.3,
        ),
        _chunk(
            source_id="rule_001",
            citation_label="Rule 1: No Harassment or Bullying",
            title="No Harassment or Bullying",
            content="Do not target harass threaten or bully.",
            distance=0.4,
        ),
    ]
    body = (
        "Please post your Twitch and YouTube self-promotion links only in the "
        "content-share channel going forward."
    )

    _, matched_rule, _ = build_citations_and_rule(
        chunks, drafted_body=body, score_threshold=0.65
    )

    assert matched_rule == "Rule 4: No Unauthorized Self-Promotion"


def test_returns_none_when_all_rules_above_threshold():
    """If every rule chunk's distance exceeds score_threshold, matched_rule is None."""
    chunks = [
        _chunk(
            source_id="rule_001",
            citation_label="Rule 1: No Harassment or Bullying",
            title="No Harassment or Bullying",
            content="Do not harass.",
            distance=0.8,  # above threshold 0.65
        ),
        _chunk(
            source_id="rule_006",
            citation_label="Rule 6: Stay On Topic",
            title="Stay On Topic",
            content="Use channels for designated purpose.",
            distance=0.9,  # above threshold 0.65
        ),
    ]
    body = "Please keep harassment out of the channel."

    _, matched_rule, _ = build_citations_and_rule(
        chunks, drafted_body=body, score_threshold=0.65
    )

    assert matched_rule is None
