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
        chunks.append(
            {
                "content": documents[i] if i < len(documents) else "",
                "source_id": doc_id,
                "citation_label": meta.get("citation_label", doc_id),
                "title": meta.get("title", ""),
                "source_type": meta.get("source_type", ""),
                "distance": distances[i] if i < len(distances) else 1.0,
            }
        )

    return chunks
