"""Shared pytest fixtures for the Esports Mod Copilot backend tests.

Provides:
- test_db: In-memory SQLite database with the same schema as database.py
- mock_provider_service: Mocks the LLM provider for predictable responses
- client: FastAPI TestClient with dependency overrides
"""

import json
import os
import tempfile

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from providers.base import ProviderResponse


# ---------------------------------------------------------------------------
# Default mock LLM responses
# ---------------------------------------------------------------------------

MOCK_FAQ_RESPONSE = ProviderResponse(
    text=(
        "The next tournament is the Spring Major Qualifier on April 19, 2026.\n\n"
        "Confidence: High - Based on official announcement."
    ),
    provider_name="mock",
    model="mock-model",
    usage={},
)

MOCK_MODERATION_RESPONSE = ProviderResponse(
    text=json.dumps(
        {
            "violation_type": "harassment",
            "matched_rule": "Rule 1: No Harassment or Bullying",
            "explanation": "Message contains targeted harassment toward another user.",
            "severity": "high",
            "suggested_action": "remove_message",
            "confidence_note": "High - clear personal attack",
        }
    ),
    provider_name="mock",
    model="mock-model",
    usage={},
)

MOCK_RETRIEVAL_CHUNKS = [
    {
        "content": "The next tournament is the Spring Major Qualifier on April 19, 2026.",
        "source_id": "faq_001",
        "citation_label": "FAQ: Tournament Schedule",
        "title": "When is the next tournament?",
        "source_type": "faq",
        "distance": 0.1,
    },
]


# ---------------------------------------------------------------------------
# Database fixture — temp file so aiosqlite works (it cannot use :memory:
# across multiple connections the way the repo code opens fresh connections).
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path):
    """Return a path to a temporary SQLite database file."""
    return str(tmp_path / "test_copilot.db")


@pytest.fixture()
def _patch_db(db_path):
    """Patch config.settings.SQLITE_PATH so all repos hit the temp DB."""
    with patch("config.settings.SQLITE_PATH", db_path):
        yield


@pytest.fixture()
def _patch_retrieval():
    """Patch retrieval_service.retrieve to return canned chunks."""
    with patch(
        "services.retrieval_service.retrieve",
        return_value=MOCK_RETRIEVAL_CHUNKS,
    ):
        yield


@pytest.fixture()
def _patch_retrieval_init():
    """Patch retrieval_service.init so startup doesn't need ChromaDB."""
    with patch("services.retrieval_service.init"):
        yield


@pytest.fixture()
def _patch_provider_faq():
    """Patch provider_service.call to return a canned FAQ answer."""
    with patch(
        "services.provider_service.call",
        new_callable=AsyncMock,
        return_value=MOCK_FAQ_RESPONSE,
    ):
        yield


@pytest.fixture()
def _patch_provider_moderation():
    """Patch provider_service.call to return a canned moderation analysis."""
    with patch(
        "services.provider_service.call",
        new_callable=AsyncMock,
        return_value=MOCK_MODERATION_RESPONSE,
    ):
        yield


# ---------------------------------------------------------------------------
# TestClient fixture — initialises the DB via the app lifespan, mocks
# heavy external deps (ChromaDB init, LLM calls).
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(db_path, _patch_retrieval_init):
    """Return a FastAPI TestClient with an in-memory DB and mocked externals.

    The lifespan handler runs init_db() which creates all tables and seeds
    the app_settings row.  ChromaDB init and LLM calls are patched out.
    """
    with patch("config.settings.SQLITE_PATH", db_path):
        # Import app *after* patching so the lifespan uses the temp DB
        from main import app
        from fastapi.testclient import TestClient

        with TestClient(app) as c:
            yield c
