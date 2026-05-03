"""Verify canonical_rule_id maps citation labels, titles, and source IDs to
the canonical rule_NNN form. The eval metrics path depends on this so it
doesn't compare ``rule_006`` against ``Rule 6: Stay On Topic`` and conclude
they're different rules."""

from __future__ import annotations

from services.utils import canonical_rule_id


def test_citation_label_normalises_to_source_id():
    assert canonical_rule_id("Rule 6: Stay On Topic") == "rule_006"


def test_title_normalises_to_source_id():
    assert canonical_rule_id("Stay On Topic") == "rule_006"


def test_source_id_passes_through():
    assert canonical_rule_id("rule_006") == "rule_006"


def test_none_returns_none():
    assert canonical_rule_id(None) is None


def test_empty_string_returns_none():
    assert canonical_rule_id("") is None


def test_unknown_label_passes_through():
    """Unknown labels pass through unchanged so the confusion matrix preserves
    information about hallucinated labels rather than collapsing them to None."""
    assert canonical_rule_id("Rule 99: Pretend Rule") == "Rule 99: Pretend Rule"


def test_account_trading_label_normalises():
    """Sanity check on the rule that drove the original Codex finding."""
    assert canonical_rule_id("Rule 8: No Account Trading or Selling") == "rule_008"
    assert canonical_rule_id("rule_008") == "rule_008"
