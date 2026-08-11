"""Provider registry."""

from __future__ import annotations

from ..config import Settings
from .base import (
    Completion,
    LLMProvider,
    ProviderError,
    StructuredCompletion,
    Usage,
)

__all__ = [
    "Completion",
    "LLMProvider",
    "ProviderError",
    "StructuredCompletion",
    "Usage",
    "build_provider",
]


def build_provider(settings: Settings) -> LLMProvider:
    """Instantiate the configured provider."""
    provider = (settings.provider or "gemini").lower()

    if provider == "mock":
        from .mock import MockProvider

        return MockProvider()

    if provider == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(settings.api_key)

    raise ProviderError(
        f"Unknown provider {provider!r}. Supported providers: gemini, mock."
    )
