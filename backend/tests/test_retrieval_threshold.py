"""Unit tests for retrieve() score_threshold filter and retrieve_split() helper.

No real Chroma — the collection.query method is mocked to return canned
distances so we can verify the post-filter and the two-call concatenation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services import retrieval_service


def _query_payload(distances: list[float], source_type: str = "rule") -> dict:
    """Build a Chroma .query() return value with len(distances) chunks."""
    n = len(distances)
    return {
        "ids": [[f"id_{i}" for i in range(n)]],
        "documents": [[f"content {i}" for i in range(n)]],
        "metadatas": [
            [
                {
                    "citation_label": f"Label {i}",
                    "title": f"Title {i}",
                    "source_type": source_type,
                }
                for i in range(n)
            ]
        ],
        "distances": [list(distances)],
    }


def test_retrieve_filters_chunks_above_threshold():
    """Chunks with distance > score_threshold are dropped post-Chroma."""
    fake_collection = MagicMock()
    fake_collection.query.return_value = _query_payload([0.4, 0.7, 0.9])

    with patch.object(retrieval_service, "_get_collection", return_value=fake_collection):
        result = retrieval_service.retrieve("query text", score_threshold=0.65)

    # Only the 0.4 chunk survives the 0.65 threshold
    assert len(result) == 1
    assert result[0]["distance"] == 0.4
    assert result[0]["source_id"] == "id_0"


def test_retrieve_no_threshold_returns_all_chunks():
    """Without score_threshold, every Chroma chunk is returned."""
    fake_collection = MagicMock()
    fake_collection.query.return_value = _query_payload([0.4, 0.7, 0.9])

    with patch.object(retrieval_service, "_get_collection", return_value=fake_collection):
        result = retrieval_service.retrieve("query text")

    assert len(result) == 3


def test_retrieve_split_makes_two_calls_and_concatenates():
    """retrieve_split issues separate Chroma queries for rules and notes,
    then concatenates the surviving chunks (rules first)."""
    call_log: list[dict] = []

    def _fake_retrieve(query, source_types=None, top_k=None, score_threshold=None):
        call_log.append(
            {
                "query": query,
                "source_types": source_types,
                "top_k": top_k,
                "score_threshold": score_threshold,
            }
        )
        if source_types == ["rule"]:
            return [{"source_id": "rule_a", "source_type": "rule"}]
        if source_types == ["mod_note"]:
            return [
                {"source_id": "note_a", "source_type": "mod_note"},
                {"source_id": "note_b", "source_type": "mod_note"},
            ]
        return []

    with patch.object(retrieval_service, "retrieve", side_effect=_fake_retrieve):
        result = retrieval_service.retrieve_split(
            "query", top_k_rules=3, top_k_notes=2, score_threshold=0.65
        )

    # Two calls: rules first, then notes
    assert len(call_log) == 2
    assert call_log[0]["source_types"] == ["rule"]
    assert call_log[0]["top_k"] == 3
    assert call_log[0]["score_threshold"] == 0.65
    assert call_log[1]["source_types"] == ["mod_note"]
    assert call_log[1]["top_k"] == 2
    assert call_log[1]["score_threshold"] == 0.65

    # Rules first, notes second, all concatenated
    assert [c["source_id"] for c in result] == ["rule_a", "note_a", "note_b"]
