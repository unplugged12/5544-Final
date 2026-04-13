"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ProviderResponse:
    """Normalised response from any LLM provider."""

    text: str
    provider_name: str
    model: str
    usage: dict = field(default_factory=dict)


class BaseLLMProvider(ABC):
    """Interface that every concrete provider must implement."""

    @abstractmethod
    async def generate_grounded_answer(
        self,
        query: str,
        context_chunks: list[dict],
        system_prompt: str,
    ) -> ProviderResponse:
        ...

    @abstractmethod
    async def generate_summary(
        self,
        text: str,
        system_prompt: str,
    ) -> ProviderResponse:
        ...

    @abstractmethod
    async def generate_mod_draft(
        self,
        situation: str,
        context_chunks: list[dict],
        system_prompt: str,
    ) -> ProviderResponse:
        ...

    @abstractmethod
    async def generate_moderation_analysis(
        self,
        message_content: str,
        rule_chunks: list[dict],
        system_prompt: str,
    ) -> ProviderResponse:
        ...
