"""Data integrity tests for the seed JSON files.

These tests validate structure, counts, and cross-references in the
data/seed/ directory.  No backend or external dependencies are needed.
"""

import json
import os
import re

import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

SEED_DIR = os.path.join(os.path.dirname(__file__), "..", "seed")


def _load(filename: str):
    """Load and parse a JSON file from the seed directory."""
    path = os.path.join(SEED_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def rules():
    return _load("rules.json")["rules"]


@pytest.fixture()
def faqs():
    return _load("faqs.json")["faqs"]


@pytest.fixture()
def announcements():
    return _load("announcements.json")["announcements"]


@pytest.fixture()
def mod_notes():
    return _load("mod_notes.json")["mod_notes"]


@pytest.fixture()
def test_toxic_messages():
    return _load("test_toxic_messages.json")["test_toxic_messages"]


@pytest.fixture()
def test_questions():
    return _load("test_questions.json")["test_questions"]


@pytest.fixture()
def test_edge_cases():
    return _load("test_edge_cases.json")["test_edge_cases"]


# ---------------------------------------------------------------------------
# 1. All JSON files parse without errors
# ---------------------------------------------------------------------------

SEED_FILES = [
    "rules.json",
    "faqs.json",
    "announcements.json",
    "mod_notes.json",
    "test_questions.json",
    "test_toxic_messages.json",
    "test_edge_cases.json",
]


@pytest.mark.parametrize("filename", SEED_FILES)
def test_json_parses_without_error(filename):
    """Every seed JSON file must parse successfully."""
    data = _load(filename)
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# 2. Exact counts
# ---------------------------------------------------------------------------

def test_rules_count(rules):
    """rules.json must contain exactly 18 rules."""
    assert len(rules) == 18


def test_faqs_count(faqs):
    """faqs.json must contain exactly 30 FAQs."""
    assert len(faqs) == 30


def test_announcements_count(announcements):
    """announcements.json must contain exactly 12 announcements."""
    assert len(announcements) == 12


def test_mod_notes_count(mod_notes):
    """mod_notes.json must contain exactly 10 mod notes."""
    assert len(mod_notes) == 10


# ---------------------------------------------------------------------------
# 3. source_id format patterns
# ---------------------------------------------------------------------------

SOURCE_ID_PATTERNS = {
    "rules.json": (r"^rule_\d{3}$", "rules"),
    "faqs.json": (r"^faq_\d{3}$", "faqs"),
    "announcements.json": (r"^ann_\d{3}$", "announcements"),
    "mod_notes.json": (r"^mod_\d{3}$", "mod_notes"),
}


@pytest.mark.parametrize(
    "filename, key",
    [
        ("rules.json", "rules"),
        ("faqs.json", "faqs"),
        ("announcements.json", "announcements"),
        ("mod_notes.json", "mod_notes"),
    ],
)
def test_source_ids_follow_format(filename, key):
    """All source_ids must match their expected pattern."""
    pattern, _ = SOURCE_ID_PATTERNS[filename]
    items = _load(filename)[key]

    for item in items:
        sid = item["source_id"]
        assert re.match(pattern, sid), (
            f"source_id '{sid}' in {filename} does not match pattern '{pattern}'"
        )


# ---------------------------------------------------------------------------
# 4. source_ids are unique within each file
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "filename, key",
    [
        ("rules.json", "rules"),
        ("faqs.json", "faqs"),
        ("announcements.json", "announcements"),
        ("mod_notes.json", "mod_notes"),
    ],
)
def test_source_ids_are_unique(filename, key):
    """No duplicate source_ids within a single file."""
    items = _load(filename)[key]
    ids = [item["source_id"] for item in items]
    assert len(ids) == len(set(ids)), f"Duplicate source_ids found in {filename}"


# ---------------------------------------------------------------------------
# 5. test_toxic_messages reference valid rules
# ---------------------------------------------------------------------------

def test_toxic_messages_reference_valid_rules(rules, test_toxic_messages):
    """Every expected_rule_match in test_toxic_messages must exist in rules.json."""
    valid_rule_ids = {r["source_id"] for r in rules}

    for msg in test_toxic_messages:
        expected = msg["expected_rule_match"]
        assert expected in valid_rule_ids, (
            f"test_toxic_messages entry '{msg['message_id']}' references "
            f"'{expected}' which is not in rules.json"
        )


# ---------------------------------------------------------------------------
# 6. Channel references use valid names
# ---------------------------------------------------------------------------

# Channels mentioned across the knowledge base
VALID_CHANNELS = {
    "#general",
    "#competitive",
    "#tournament-info",
    "#tournament-signup",
    "#tournament-rules",
    "#match-results",
    "#ranked-lfg",
    "#content-share",
    "#leaks-spoilers",
    "#memes",
    "#bot-commands",
    "#clan-recruitment",
    "#international",
    "#appeals",
    "#dispute-resolution",
    "#mod-applications",
    "#mod-discussion",
    "#mod-log",
    "#report-cheaters",
    "#rank-verify",
    "#verify",
    "#streaming",
    "#rules",
    "#announcements",
}


def _extract_channels(text: str) -> set[str]:
    """Extract all #channel-name references from text."""
    return set(re.findall(r"#[a-z][a-z0-9_-]*", text))


@pytest.mark.parametrize(
    "filename, key, text_fields",
    [
        ("rules.json", "rules", ["description"]),
        ("faqs.json", "faqs", ["answer"]),
        ("announcements.json", "announcements", ["content"]),
        ("mod_notes.json", "mod_notes", ["content"]),
    ],
)
def test_channel_references_are_valid(filename, key, text_fields):
    """All #channel references in seed data must be in the known channel set."""
    items = _load(filename)[key]

    for item in items:
        for field in text_fields:
            text = item.get(field, "")
            channels = _extract_channels(text)
            for ch in channels:
                assert ch in VALID_CHANNELS, (
                    f"Unknown channel '{ch}' found in {filename} "
                    f"item '{item.get('source_id', 'unknown')}' field '{field}'"
                )


# ---------------------------------------------------------------------------
# 7. Required fields present in each data type
# ---------------------------------------------------------------------------

def test_rules_have_required_fields(rules):
    """Each rule must have source_id, title, description, category, tags, citation_label."""
    required = {"source_id", "title", "description", "category", "tags", "citation_label"}
    for rule in rules:
        missing = required - set(rule.keys())
        assert not missing, (
            f"Rule '{rule.get('source_id')}' missing fields: {missing}"
        )


def test_faqs_have_required_fields(faqs):
    """Each FAQ must have source_id, question, answer, category, tags, citation_label."""
    required = {"source_id", "question", "answer", "category", "tags", "citation_label"}
    for faq in faqs:
        missing = required - set(faq.keys())
        assert not missing, (
            f"FAQ '{faq.get('source_id')}' missing fields: {missing}"
        )


def test_announcements_have_required_fields(announcements):
    """Each announcement must have source_id, title, content, date, category, tags."""
    required = {"source_id", "title", "content", "date", "category", "tags", "citation_label"}
    for ann in announcements:
        missing = required - set(ann.keys())
        assert not missing, (
            f"Announcement '{ann.get('source_id')}' missing fields: {missing}"
        )


def test_mod_notes_have_required_fields(mod_notes):
    """Each mod note must have source_id, title, content, context, tags."""
    required = {"source_id", "title", "content", "context", "tags", "citation_label"}
    for note in mod_notes:
        missing = required - set(note.keys())
        assert not missing, (
            f"Mod note '{note.get('source_id')}' missing fields: {missing}"
        )


def test_toxic_messages_have_required_fields(test_toxic_messages):
    """Each toxic message must have message_id, content, expected_violation_type, expected_severity, expected_rule_match."""
    required = {
        "message_id",
        "content",
        "expected_violation_type",
        "expected_severity",
        "expected_rule_match",
    }
    for msg in test_toxic_messages:
        missing = required - set(msg.keys())
        assert not missing, (
            f"Toxic message '{msg.get('message_id')}' missing fields: {missing}"
        )


# ---------------------------------------------------------------------------
# 8. Tags are non-empty lists of strings
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "filename, key",
    [
        ("rules.json", "rules"),
        ("faqs.json", "faqs"),
        ("announcements.json", "announcements"),
        ("mod_notes.json", "mod_notes"),
    ],
)
def test_tags_are_nonempty_string_lists(filename, key):
    """Tags field must be a non-empty list of strings."""
    items = _load(filename)[key]

    for item in items:
        tags = item.get("tags", [])
        assert isinstance(tags, list), (
            f"Tags in {filename} item '{item.get('source_id')}' is not a list"
        )
        assert len(tags) > 0, (
            f"Tags in {filename} item '{item.get('source_id')}' is empty"
        )
        for tag in tags:
            assert isinstance(tag, str), (
                f"Tag '{tag}' in {filename} item '{item.get('source_id')}' is not a string"
            )
