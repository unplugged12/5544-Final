"""Verify the OpenAI provider's temperature-kwargs helper drops the param
for GPT-5 family models (which reject anything other than the default 1)
while preserving it for other model families.
"""

from __future__ import annotations

from providers.openai_provider import _temperature_kwargs


def test_gpt5_family_omits_temperature():
    assert _temperature_kwargs("gpt-5-nano-2025-08-07", 0.2) == {}
    assert _temperature_kwargs("gpt-5", 0.5) == {}
    assert _temperature_kwargs("gpt-5-mini", 0.3) == {}


def test_gpt4_family_keeps_temperature():
    assert _temperature_kwargs("gpt-4o-mini", 0.2) == {"temperature": 0.2}
    assert _temperature_kwargs("gpt-4o", 0.4) == {"temperature": 0.4}
    assert _temperature_kwargs("gpt-4-turbo", 0.5) == {"temperature": 0.5}


def test_o1_family_keeps_temperature():
    # o1 isn't in our exclusion list — it accepts temperature normally
    assert _temperature_kwargs("o1-mini", 0.3) == {"temperature": 0.3}


def test_unknown_model_keeps_temperature():
    assert _temperature_kwargs("some-future-model", 0.5) == {"temperature": 0.5}
