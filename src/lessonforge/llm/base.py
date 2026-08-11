"""Provider abstraction.

The graph never imports a vendor SDK. It talks to this protocol, which buys two
things that matter for this system specifically:

* the whole pipeline runs offline against `MockProvider`, so tests and CI need
  no API key and no network;
* swapping Gemini for another vendor is one file, not a refactor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class Usage:
    """Token accounting, aggregated across a run."""

    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            calls=self.calls + other.calls,
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "calls": self.calls,
        }


@dataclass
class Completion:
    """A text response plus what it cost."""

    text: str
    usage: Usage = field(default_factory=Usage)
    model: str = ""


@dataclass
class StructuredCompletion:
    """A schema-validated response plus what it cost."""

    parsed: Any
    raw_text: str = ""
    usage: Usage = field(default_factory=Usage)
    model: str = ""


class LLMProvider(Protocol):
    """Minimal surface the graph depends on."""

    name: str

    def complete(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 16000,
    ) -> Completion:
        """Free-form text generation."""
        ...

    def complete_structured(
        self,
        *,
        model: str,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 16000,
    ) -> StructuredCompletion:
        """Generation constrained to a Pydantic schema.

        The evaluator depends on this: a judge that can reply in prose is a judge
        that will eventually reply in prose, at 2am, in production.
        """
        ...


class ProviderError(RuntimeError):
    """Raised when a provider call fails in a way the graph should surface."""
