"""Shared utilities for provider modules."""


def format_chunks(chunks: list[dict]) -> str:
    """Build a labelled context block from retrieved chunks."""
    parts: list[str] = []
    for chunk in chunks:
        label = chunk.get("citation_label", chunk.get("source_id", "unknown"))
        content = chunk.get("content", "")
        parts.append(f"[{label}]: {content}")
    return "\n\n".join(parts)
