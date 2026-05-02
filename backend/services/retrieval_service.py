"""ChromaDB retrieval service for knowledge base lookups."""

import logging

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from config import settings

logger = logging.getLogger(__name__)

_collection = None


def _get_collection():
    """Lazy-initialise and return the Chroma collection singleton."""
    global _collection
    if _collection is None:
        logger.info(
            "Initializing Chroma PersistentClient at %s", settings.CHROMA_PERSIST_DIR
        )
        client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        ef = SentenceTransformerEmbeddingFunction(
            model_name=settings.EMBEDDING_MODEL
        )
        _collection = client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            embedding_function=ef,
        )
        logger.info(
            "Chroma collection '%s' loaded — %d documents",
            settings.CHROMA_COLLECTION,
            _collection.count(),
        )
    return _collection


def init() -> None:
    """Eagerly initialise the collection (called at startup)."""
    _get_collection()


def retrieve(
    query: str,
    source_types: list[str] | None = None,
    top_k: int | None = None,
    score_threshold: float | None = None,
) -> list[dict]:
    """Retrieve the top-k most relevant chunks for *query*.

    Returns a list of dicts with keys:
        content, source_id, citation_label, title, source_type, distance
    """
    if top_k is None:
        top_k = settings.TOP_K_RESULTS

    collection = _get_collection()

    where_filter = None
    if source_types:
        where_filter = {"source_type": {"$in": source_types}}

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[dict] = []
    if not results or not results.get("ids"):
        return chunks

    ids = results["ids"][0]
    documents = results["documents"][0] if results.get("documents") else []
    metadatas = results["metadatas"][0] if results.get("metadatas") else []
    distances = results["distances"][0] if results.get("distances") else []

    for i, doc_id in enumerate(ids):
        meta = metadatas[i] if i < len(metadatas) else {}
        distance = distances[i] if i < len(distances) else 1.0
        if score_threshold is not None and distance > score_threshold:
            continue
        chunks.append(
            {
                "content": documents[i] if i < len(documents) else "",
                "source_id": doc_id,
                "citation_label": meta.get("citation_label", doc_id),
                "title": meta.get("title", ""),
                "source_type": meta.get("source_type", ""),
                "distance": distance,
            }
        )

    return chunks


def retrieve_split(
    query: str,
    top_k_rules: int,
    top_k_notes: int,
    score_threshold: float | None = None,
) -> list[dict]:
    """Retrieve rules and mod_notes via separate Chroma calls and concatenate.

    Pooled rules+notes retrieval lets densely-worded mod_notes crowd out rule
    chunks; splitting guarantees up to top_k_rules rules survive when notes
    score better on similarity.
    """
    rule_chunks = retrieve(
        query=query,
        source_types=["rule"],
        top_k=top_k_rules,
        score_threshold=score_threshold,
    )
    note_chunks = retrieve(
        query=query,
        source_types=["mod_note"],
        top_k=top_k_notes,
        score_threshold=score_threshold,
    )
    return rule_chunks + note_chunks
