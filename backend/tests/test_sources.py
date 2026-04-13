"""Tests for GET /api/sources endpoint."""

import aiosqlite
import pytest


def _seed_knowledge_items(db_path: str):
    """Insert a few knowledge items into the test DB synchronously.

    We use a raw synchronous sqlite3 connection here because the test DB is
    already initialised by the TestClient lifespan (tables exist).
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.executemany(
        """
        INSERT OR IGNORE INTO knowledge_items
            (source_id, source_type, title, content, category, tags, citation_label)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "rule_001",
                "rule",
                "No Harassment or Bullying",
                "Do not harass or bully any member.",
                "conduct",
                '["harassment","bullying"]',
                "Rule 1: No Harassment or Bullying",
            ),
            (
                "faq_001",
                "faq",
                "When is the next tournament?",
                "Spring Major Qualifier on April 19, 2026.",
                "tournaments",
                '["tournament","schedule"]',
                "FAQ: Tournament Schedule",
            ),
            (
                "ann_001",
                "announcement",
                "Spring Major Qualifier Registration Open",
                "Registration is now open.",
                "tournament",
                '["tournament","spring-major"]',
                "Announcement: Spring Major Qualifier",
            ),
        ],
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def seeded_client(client, db_path):
    """A TestClient with knowledge items already seeded."""
    _seed_knowledge_items(db_path)
    return client


def test_sources_returns_200(client):
    """GET /api/sources should return 200 even when empty."""
    response = client.get("/api/sources")
    assert response.status_code == 200

    data = response.json()
    assert "sources" in data
    assert "total" in data
    assert data["total"] == 0


def test_sources_returns_seeded_items(seeded_client):
    """GET /api/sources returns all seeded knowledge items."""
    response = seeded_client.get("/api/sources")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 3
    assert len(data["sources"]) == 3


def test_sources_filter_by_type(seeded_client):
    """GET /api/sources?source_type=rule returns only rules."""
    response = seeded_client.get("/api/sources", params={"source_type": "rule"})
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert data["sources"][0]["source_type"] == "rule"
    assert data["sources"][0]["source_id"] == "rule_001"


def test_sources_filter_by_faq(seeded_client):
    """GET /api/sources?source_type=faq returns only FAQs."""
    response = seeded_client.get("/api/sources", params={"source_type": "faq"})
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert data["sources"][0]["source_type"] == "faq"


def test_sources_filter_invalid_type(client):
    """GET /api/sources with an invalid source_type returns 422."""
    response = client.get("/api/sources", params={"source_type": "invalid"})
    assert response.status_code == 422


def test_sources_item_shape(seeded_client):
    """Each source item has all expected fields."""
    data = seeded_client.get("/api/sources").json()
    item = data["sources"][0]

    expected_fields = {
        "source_id",
        "source_type",
        "title",
        "content",
        "category",
        "tags",
        "citation_label",
        "created_at",
    }
    assert expected_fields.issubset(set(item.keys()))
    assert isinstance(item["tags"], list)
