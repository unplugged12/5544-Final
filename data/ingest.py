"""
CDL Ranked Discord -- Knowledge Base Ingestion Script

Reads seed JSON files, stores structured records in SQLite, chunks text,
and embeds into ChromaDB for vector retrieval.

Usage:
    python data/ingest.py
"""

import json
import os
import sqlite3
import sys

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


# ---------------------------------------------------------------------------
# Paths (relative to project root)
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SEED_DIR = os.path.join(SCRIPT_DIR, "seed")
DB_PATH = os.path.join(SCRIPT_DIR, "copilot.db")
CHROMA_DIR = os.path.join(SCRIPT_DIR, "chroma")

RULES_PATH = os.path.join(SEED_DIR, "rules.json")
FAQS_PATH = os.path.join(SEED_DIR, "faqs.json")
ANNOUNCEMENTS_PATH = os.path.join(SEED_DIR, "announcements.json")
MOD_NOTES_PATH = os.path.join(SEED_DIR, "mod_notes.json")
TOXIC_MESSAGES_PATH = os.path.join(SEED_DIR, "test_toxic_messages.json")

COLLECTION_NAME = "knowledge_base"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Announcement chunk parameters
MAX_CHUNK_CHARS = 500
TARGET_CHUNK_CHARS = 400
OVERLAP_CHARS = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: str) -> dict:
    """Load and return parsed JSON from *path*."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def split_into_sentences(text: str) -> list[str]:
    """Naive sentence splitter on `. `, `! `, `? ` boundaries."""
    sentences: list[str] = []
    current = ""
    for char in text:
        current += char
        if char in ".!?" and current.strip():
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())
    return sentences


def chunk_long_text(text: str, max_chars: int = MAX_CHUNK_CHARS,
                    target_chars: int = TARGET_CHUNK_CHARS,
                    overlap_chars: int = OVERLAP_CHARS) -> list[str]:
    """Split *text* at sentence boundaries into ~target_chars chunks with overlap.

    If *text* is shorter than *max_chars* it is returned as a single chunk.
    """
    if len(text) <= max_chars:
        return [text]

    sentences = split_into_sentences(text)
    chunks: list[str] = []
    current_chunk = ""
    overlap_buffer = ""

    for sentence in sentences:
        if current_chunk and len(current_chunk) + len(sentence) + 1 > target_chars:
            chunks.append(current_chunk.strip())
            # Build overlap from the end of the current chunk
            overlap_buffer = current_chunk.strip()[-overlap_chars:]
            current_chunk = overlap_buffer + " " + sentence
        else:
            current_chunk = (current_chunk + " " + sentence).strip()

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# ---------------------------------------------------------------------------
# SQLite setup
# ---------------------------------------------------------------------------

def init_sqlite(db_path: str) -> sqlite3.Connection:
    """Create (or connect to) the SQLite database and ensure the schema."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_items (
            source_id    TEXT PRIMARY KEY,
            source_type  TEXT NOT NULL CHECK(source_type IN ('rule','faq','announcement','mod_note')),
            title        TEXT NOT NULL,
            content      TEXT NOT NULL,
            category     TEXT,
            tags         TEXT NOT NULL DEFAULT '[]',
            citation_label TEXT NOT NULL,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    return conn


def clear_sqlite(conn: sqlite3.Connection) -> None:
    """Delete all rows from knowledge_items for idempotent re-ingestion."""
    conn.execute("DELETE FROM knowledge_items;")
    conn.commit()


def insert_item(conn: sqlite3.Connection, source_id: str, source_type: str,
                title: str, content: str, category: str | None,
                tags: list[str], citation_label: str) -> None:
    """Insert a single knowledge item into SQLite."""
    conn.execute(
        """INSERT INTO knowledge_items
           (source_id, source_type, title, content, category, tags, citation_label)
           VALUES (?, ?, ?, ?, ?, ?, ?);""",
        (source_id, source_type, title, content, category,
         json.dumps(tags), citation_label),
    )


# ---------------------------------------------------------------------------
# Chroma setup
# ---------------------------------------------------------------------------

def init_chroma(chroma_dir: str):
    """Create a PersistentClient and a fresh collection with SentenceTransformer embeddings."""
    client = chromadb.PersistentClient(path=chroma_dir)

    # Delete existing collection for idempotency
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # Collection may not exist on first run

    embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )
    return client, collection


# ---------------------------------------------------------------------------
# Ingestion logic per source type
# ---------------------------------------------------------------------------

def ingest_rules(conn: sqlite3.Connection, collection, path: str) -> tuple[int, int]:
    """Ingest rules.json. Returns (item_count, chunk_count)."""
    data = load_json(path)
    items = data["rules"]
    ids, documents, metadatas = [], [], []

    for item in items:
        source_id = item["source_id"]
        title = item["title"]
        description = item["description"]
        category = item.get("category")
        tags = item.get("tags", [])
        citation_label = item["citation_label"]
        rule_number = item["rule_number"]

        # SQLite
        insert_item(conn, source_id, "rule", title, description,
                    category, tags, citation_label)

        # Chunk text
        chunk_text = f"Rule {rule_number}: {title}\n{description}"
        chunk_id = f"{source_id}_chunk_0"
        ids.append(chunk_id)
        documents.append(chunk_text)
        metadatas.append({
            "source_id": source_id,
            "source_type": "rule",
            "title": title,
            "citation_label": citation_label,
            "category": category or "",
            "chunk_index": 0,
        })

    conn.commit()
    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(items), len(ids)


def ingest_faqs(conn: sqlite3.Connection, collection, path: str) -> tuple[int, int]:
    """Ingest faqs.json. Returns (item_count, chunk_count)."""
    data = load_json(path)
    items = data["faqs"]
    ids, documents, metadatas = [], [], []

    for item in items:
        source_id = item["source_id"]
        question = item["question"]
        answer = item["answer"]
        category = item.get("category")
        tags = item.get("tags", [])
        citation_label = item["citation_label"]

        # SQLite
        insert_item(conn, source_id, "faq", question, answer,
                    category, tags, citation_label)

        # Chunk text
        chunk_text = f"Q: {question}\nA: {answer}"
        chunk_id = f"{source_id}_chunk_0"
        ids.append(chunk_id)
        documents.append(chunk_text)
        metadatas.append({
            "source_id": source_id,
            "source_type": "faq",
            "title": question,
            "citation_label": citation_label,
            "category": category or "",
            "chunk_index": 0,
        })

    conn.commit()
    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(items), len(ids)


def ingest_announcements(conn: sqlite3.Connection, collection, path: str) -> tuple[int, int]:
    """Ingest announcements.json. Returns (item_count, chunk_count)."""
    data = load_json(path)
    items = data["announcements"]
    ids, documents, metadatas = [], [], []

    for item in items:
        source_id = item["source_id"]
        title = item["title"]
        content = item["content"]
        category = item.get("category")
        tags = item.get("tags", [])
        citation_label = item["citation_label"]

        # SQLite
        insert_item(conn, source_id, "announcement", title, content,
                    category, tags, citation_label)

        # Chunk text -- split long announcements
        full_text = f"{title}\n{content}"
        chunks = chunk_long_text(full_text)

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{source_id}_chunk_{idx}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({
                "source_id": source_id,
                "source_type": "announcement",
                "title": title,
                "citation_label": citation_label,
                "category": category or "",
                "chunk_index": idx,
            })

    conn.commit()
    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(items), len(ids)


def ingest_mod_notes(conn: sqlite3.Connection, collection, path: str) -> tuple[int, int]:
    """Ingest mod_notes.json. Returns (item_count, chunk_count)."""
    data = load_json(path)
    items = data["mod_notes"]
    ids, documents, metadatas = [], [], []

    for item in items:
        source_id = item["source_id"]
        title = item["title"]
        content = item["content"]
        category = item.get("context")  # mod_notes use "context" field
        tags = item.get("tags", [])
        citation_label = item["citation_label"]

        # SQLite
        insert_item(conn, source_id, "mod_note", title, content,
                    category, tags, citation_label)

        # Chunk text
        chunk_text = f"{title}\n{content}"
        chunk_id = f"{source_id}_chunk_0"
        ids.append(chunk_id)
        documents.append(chunk_text)
        metadatas.append({
            "source_id": source_id,
            "source_type": "mod_note",
            "title": title,
            "citation_label": citation_label,
            "category": category or "",
            "chunk_index": 0,
        })

    conn.commit()
    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(items), len(ids)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_toxic_rule_matches(conn: sqlite3.Connection, toxic_path: str) -> tuple[int, int]:
    """Check that every expected_rule_match in test_toxic_messages.json
    exists in the knowledge_items table.

    Returns (pass_count, fail_count).
    """
    data = load_json(toxic_path)
    messages = data["test_toxic_messages"]
    cursor = conn.cursor()

    pass_count = 0
    fail_count = 0

    for msg in messages:
        rule_id = msg["expected_rule_match"]
        cursor.execute(
            "SELECT 1 FROM knowledge_items WHERE source_id = ?;",
            (rule_id,),
        )
        if cursor.fetchone():
            pass_count += 1
        else:
            fail_count += 1
            print(f"  FAIL: {msg['message_id']} references {rule_id} -- not found in knowledge_items")

    return pass_count, fail_count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("CDL Ranked Discord -- Knowledge Base Ingestion")
    print("=" * 60)

    # --- SQLite ---
    print(f"\n[1/6] Initializing SQLite database at {DB_PATH}")
    conn = init_sqlite(DB_PATH)
    clear_sqlite(conn)

    # --- Chroma ---
    print(f"[2/6] Initializing ChromaDB at {CHROMA_DIR}")
    print(f"       Embedding model: {EMBEDDING_MODEL}")
    _client, collection = init_chroma(CHROMA_DIR)

    # --- Ingest each source ---
    print("\n[3/6] Ingesting seed data...")

    rule_items, rule_chunks = ingest_rules(conn, collection, RULES_PATH)
    print(f"  Rules:         {rule_items:>3} items, {rule_chunks:>3} chunks")

    faq_items, faq_chunks = ingest_faqs(conn, collection, FAQS_PATH)
    print(f"  FAQs:          {faq_items:>3} items, {faq_chunks:>3} chunks")

    ann_items, ann_chunks = ingest_announcements(conn, collection, ANNOUNCEMENTS_PATH)
    print(f"  Announcements: {ann_items:>3} items, {ann_chunks:>3} chunks")

    mod_items, mod_chunks = ingest_mod_notes(conn, collection, MOD_NOTES_PATH)
    print(f"  Mod Notes:     {mod_items:>3} items, {mod_chunks:>3} chunks")

    total_items = rule_items + faq_items + ann_items + mod_items
    total_chunks = rule_chunks + faq_chunks + ann_chunks + mod_chunks
    print(f"\n[4/6] Totals: {total_items} items in SQLite, {total_chunks} chunks in Chroma")

    # --- Validation ---
    print("\n[5/6] Validating toxic message rule references...")
    pass_count, fail_count = validate_toxic_rule_matches(conn, TOXIC_MESSAGES_PATH)
    print(f"  Results: {pass_count} passed, {fail_count} failed")

    # --- Cleanup ---
    conn.close()

    print("\n[6/6] Ingestion complete!")
    print("=" * 60)

    if fail_count > 0:
        print(f"\nWARNING: {fail_count} toxic message(s) reference invalid rule IDs.")
        sys.exit(1)
    else:
        print("\nAll validations passed.")


if __name__ == "__main__":
    main()
