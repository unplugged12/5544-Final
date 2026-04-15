"""Tests for chat_prompt.py — system prompt integrity checks.

PR 6's adversarial suite needs SYSTEM_PROMPT_HEADER to assert that replies
never contain the first 40 chars of the prompt (exfiltration check).
"""

import pytest

from prompts.chat_prompt import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_HEADER,
    get_system_prompt,
    get_system_prompt_header,
)


class TestGetSystemPrompt:
    def test_returns_nonempty_string(self):
        result = get_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_identity_lock_marker(self):
        result = get_system_prompt()
        assert "IDENTITY LOCK" in result

    def test_contains_user_message_delimiter(self):
        result = get_system_prompt()
        assert "<<<USER_MESSAGE" in result

    def test_contains_in_character_refusal_phrase(self):
        # Plan specifies this exact phrase for the system-prompt-exfil refusal
        result = get_system_prompt()
        assert "cant show my playbook" in result

    def test_constant_and_function_agree(self):
        assert get_system_prompt() == SYSTEM_PROMPT


class TestSystemPromptHeader:
    def test_header_is_exactly_40_chars(self):
        assert len(SYSTEM_PROMPT_HEADER) == 40

    def test_header_is_prefix_of_full_prompt(self):
        assert SYSTEM_PROMPT.startswith(SYSTEM_PROMPT_HEADER)

    def test_get_system_prompt_header_function(self):
        assert get_system_prompt_header() == SYSTEM_PROMPT_HEADER

    def test_header_function_returns_40_chars(self):
        assert len(get_system_prompt_header()) == 40


class TestSystemPromptContent:
    """Spot-check key sections required by the plan's prompt design."""

    def test_contains_tone_section(self):
        assert "TONE" in get_system_prompt()

    def test_contains_scope_section(self):
        assert "SCOPE" in get_system_prompt()

    def test_contains_refusal_style_section(self):
        assert "REFUSAL STYLE" in get_system_prompt()

    def test_contains_user_claims_section(self):
        assert "USER CLAIMS" in get_system_prompt()

    def test_contains_untrusted_data_note(self):
        assert "UNTRUSTED DATA" in get_system_prompt()

    def test_modbot_identity(self):
        assert "ModBot" in get_system_prompt()
