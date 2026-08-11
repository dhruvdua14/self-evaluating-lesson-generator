"""Google Gemini provider (google-genai SDK)."""

from __future__ import annotations

import json
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .base import Completion, LLMProvider, ProviderError, StructuredCompletion, Usage

T = TypeVar("T", bound=BaseModel)

_RETRYABLE_MARKERS = (
    "429", "500", "502", "503", "504",
    "resource_exhausted", "unavailable", "internal", "deadline",
    "overloaded", "rate limit", "quota",
)


def _is_retryable(exc: Exception) -> bool:
    blob = f"{type(exc).__name__} {exc}".lower()
    return any(marker in blob for marker in _RETRYABLE_MARKERS)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None, *, max_attempts: int = 4) -> None:
        if not api_key:
            raise ProviderError(
                "No Gemini API key found. Set GEMINI_API_KEY in your environment "
                "or .env file, or run with --provider mock to use the offline "
                "deterministic provider."
            )
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - import guard
            raise ProviderError(
                "google-genai is not installed. Run: pip install google-genai"
            ) from exc

        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self._max_attempts = max_attempts

    # ------------------------------------------------------------------ utils

    def list_models(self) -> list[str]:
        """Names of models on this key that can actually generate content."""
        names: list[str] = []
        for m in self._client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if actions and "generateContent" not in actions:
                continue
            name = (m.name or "").removeprefix("models/")
            if name:
                names.append(name)
        return sorted(names)

    def _usage(self, response) -> Usage:
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return Usage(calls=1)
        return Usage(
            input_tokens=getattr(meta, "prompt_token_count", 0) or 0,
            # thoughts_token_count is billed as output on thinking models, so it
            # belongs in this number or the run's cost report understates itself.
            output_tokens=(getattr(meta, "candidates_token_count", 0) or 0)
            + (getattr(meta, "thoughts_token_count", 0) or 0),
            calls=1,
        )

    def _call(self, *, model: str, contents: str, config):
        """Invoke the API with bounded exponential backoff on transient errors."""
        last: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                return self._client.models.generate_content(
                    model=model, contents=contents, config=config
                )
            except Exception as exc:  # noqa: BLE001 - vendor raises broad types
                last = exc
                if not _is_retryable(exc) or attempt == self._max_attempts - 1:
                    raise ProviderError(f"Gemini call to {model} failed: {exc}") from exc
                time.sleep(min(2**attempt, 8))
        raise ProviderError(f"Gemini call to {model} failed: {last}")

    # ------------------------------------------------------------------- API

    def complete(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 16000,
    ) -> Completion:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        response = self._call(model=model, contents=prompt, config=config)
        text = response.text
        if not text:
            raise ProviderError(
                f"Gemini returned no text for {model}. "
                f"finish_reason={_finish_reason(response)}"
            )
        return Completion(text=text, usage=self._usage(response), model=model)

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
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
            response_schema=schema,
        )
        response = self._call(model=model, contents=prompt, config=config)
        usage = self._usage(response)

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, schema):
            return StructuredCompletion(
                parsed=parsed, raw_text=response.text or "", usage=usage, model=model
            )

        # The SDK usually parses for us. When it doesn't (schema edge cases,
        # truncation) we validate the raw JSON ourselves rather than silently
        # returning None — a judge that returns nothing must be a loud failure,
        # never an implicit pass.
        raw = response.text or ""
        if not raw.strip():
            raise ProviderError(
                f"Judge model {model} returned an empty response "
                f"(finish_reason={_finish_reason(response)}). Cannot evaluate."
            )
        try:
            return StructuredCompletion(
                parsed=schema.model_validate(json.loads(raw)),
                raw_text=raw,
                usage=usage,
                model=model,
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ProviderError(
                f"Judge model {model} returned unparseable JSON: {exc}\n"
                f"---\n{raw[:600]}"
            ) from exc


def _finish_reason(response) -> str:
    try:
        return str(response.candidates[0].finish_reason)
    except Exception:  # noqa: BLE001
        return "unknown"
