"""Google Gemini provider (google-genai SDK)."""

from __future__ import annotations

import json
import re
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


def _is_rate_limit(exc: Exception) -> bool:
    blob = f"{exc}".lower()
    return "429" in blob or "resource_exhausted" in blob or "rate limit" in blob


_RETRY_DELAY_RE = re.compile(r"retrydelay['\"]?\s*[:=]\s*['\"]?(\d+)s", re.IGNORECASE)


def _backoff_seconds(exc: Exception, attempt: int) -> float:
    """How long to wait before the next attempt.

    Honours the server's own `retryDelay` when it supplies one — guessing is
    strictly worse than being told. Otherwise: rate limits get a long,
    minute-scale wait because that is the window they are measured over;
    everything else gets ordinary short exponential backoff.
    """
    match = _RETRY_DELAY_RE.search(str(exc))
    if match:
        # Small cushion so we resume just after the window, not exactly on it.
        return min(float(match.group(1)) + 2, 90.0)

    if _is_rate_limit(exc):
        return min(30.0 * (attempt + 1), 90.0)

    return min(2.0**attempt, 8.0)


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
        """Invoke the API with backoff sized to the error, not a single curve.

        Rate limits and transient server errors need very different waits. A
        429 on a per-minute quota needs to outlast the window — roughly 60s —
        while a 503 usually clears in seconds. An 8-second ceiling for both
        looks like resilience and delivers none: every judge call in a run
        fails, every check is recorded as failed, and the system reports a
        confident verdict about content nobody evaluated.
        """
        last: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                return self._client.models.generate_content(
                    model=model, contents=contents, config=config
                )
            except Exception as exc:  # noqa: BLE001 - vendor raises broad types
                last = exc
                if not _is_retryable(exc) or attempt == self._max_attempts - 1:
                    raise ProviderError(_explain(model, exc)) from exc
                time.sleep(_backoff_seconds(exc, attempt))
        raise ProviderError(_explain(model, last))

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


def _explain(model: str, exc: Exception | None) -> str:
    """Turn a raw vendor error into something the user can act on.

    The two failures people actually hit are a model their key cannot see and a
    model their key has no quota for. Both are recoverable in one command, so
    the message says which command rather than just echoing the HTTP code.
    """
    blob = str(exc)
    base = f"Gemini call to {model!r} failed: {blob}"

    if "404" in blob or "NOT_FOUND" in blob:
        return (
            f"Model {model!r} is not available on this API key (404).\n\n"
            f"Run `lessonforge models` to list the models your key can reach, "
            f"then set the matching LF_*_MODEL variable in your .env.\n\n"
            f"Original error: {blob[:300]}"
        )

    if "429" in blob or "RESOURCE_EXHAUSTED" in blob:
        return (
            f"Model {model!r} returned 429 — your key has no remaining quota for "
            f"it (free Google AI Studio keys typically have zero quota for "
            f"pro-tier models).\n\n"
            f"Either wait for the quota window to reset, or switch to a "
            f"flash-tier model in your .env, e.g.:\n"
            f"    LF_GENERATOR_MODEL=gemini-3.6-flash\n"
            f"    LF_JUDGE_MODEL=gemini-3.6-flash\n\n"
            f"Run `lessonforge models` to see the full list.\n\n"
            f"Original error: {blob[:300]}"
        )

    return base


def _finish_reason(response) -> str:
    try:
        return str(response.candidates[0].finish_reason)
    except Exception:  # noqa: BLE001
        return "unknown"
