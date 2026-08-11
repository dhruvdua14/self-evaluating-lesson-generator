"""Deterministic offline provider.

This exists so the entire agentic loop — plan, generate, evaluate, regenerate,
reflect, persist — runs end to end with no API key, no network, and no cost.
CI uses it. So does anyone who clones the repo before getting a key.

It is not a stub that returns "ok". It replays a scripted failure: the first
draft is genuinely bad and genuinely fails the rubric, the second is genuinely
good and genuinely passes. The retry path is therefore exercised for real, and
the deterministic checks run against real text either way.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from ..models import LessonPlan, PatchProposal, ReflectionOutput
from ..rubric.schema import JudgeCheck, JudgeVerdict
from .base import Completion, LLMProvider, ProviderError, StructuredCompletion, Usage

T = TypeVar("T", bound=BaseModel)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / f"{name}.md").read_text(encoding="utf-8")


# Sentinel phrases the mock judge treats as violations. These mirror the real
# rubric's intent closely enough that the mock run is a meaningful rehearsal.
_FORBIDDEN_CLAIMS = {
    "no_weight_update_myth": (
        "absorbs that knowledge into its weights",
        "becomes part of the model itself",
        "fine-tuned on your documents",
        "model learns your documents",
        "stored inside the model",
    ),
    "accuracy_grounded": (
        "completely eliminates hallucination",
        "guarantees that every answer",
        "vector database is mandatory",
        "retrieval is simply not possible",
    ),
    "no_unsupported_claims": (
        "47%",
        "3.2x",
        "according to benchmarks",
    ),
    "no_idioms_or_cultural_refs": (
        "at the end of the day",
        "silver bullet",
        "home run",
        "out of the box",
        "pretty much",
    ),
    "standalone_completeness": (
        "recall from the previous module",
        "as we saw in the last lesson",
        "previous module",
    ),
    "no_forward_references": (
        "as we will see later",
        "we will cover this later",
        "later in this course",
        "we will explain",
        "for now just",
    ),
    "jargon_defined_on_first_use": (
        "bi-encoder",
        "approximate nearest-neighbour",
        "latent manifolds",
        "high-dimensional",
    ),
}

# Presence checks come in two flavours and conflating them breaks the mock.
#
# ANY: one marker is sufficient evidence. A lesson needs *an* analogy, not four
# specific phrasings — demanding all of them fails perfectly good lessons.
_REQUIRED_ANY = {
    "has_concrete_analogy": ("think of it like", "imagine", "just like", "picture a"),
    "has_recap": ("recap", "summary", "to remember"),
}

# ALL: every marker must survive.
#
# These key on *substance*, not on headings. An earlier version checked
# `covers_what_why_how` against the strings "how it works" and "step by step" —
# i.e. section titles — and duly "caught" an injection that deleted those
# headings while leaving the actual explanation of retrieve/augment/generate
# intact elsewhere in the lesson. The live judge read for substance and
# correctly refused to fail it, so the mock was manufacturing a green the real
# evaluator would not give. A mock that disagrees with reality in the lenient
# direction hides gaps; in the strict direction it invents them. Both are worse
# than no mock.
_REQUIRED_ALL = {
    "has_worked_example": ("step one", "step two", "step three"),
    "covers_what_why_how": ("retriev", "augment", "generat"),
}


class MockProvider(LLMProvider):
    """Scripted, deterministic, offline."""

    name = "mock"

    def __init__(self, *, fail_first: bool = True) -> None:
        self.fail_first = fail_first
        self.generation_calls = 0
        self.judge_calls = 0

    # ------------------------------------------------------------------ text

    def complete(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 16000,
    ) -> Completion:
        """Only the generator uses free-form completion."""
        self.generation_calls += 1
        first_attempt = self.generation_calls == 1
        draft = "draft_bad" if (first_attempt and self.fail_first) else "draft_good"
        text = _load(draft)
        return Completion(
            text=text,
            usage=Usage(input_tokens=len(prompt) // 4, output_tokens=len(text) // 4, calls=1),
            model=f"mock:{model}",
        )

    # ------------------------------------------------------------ structured

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
        usage = Usage(input_tokens=len(prompt) // 4, output_tokens=120, calls=1)

        if schema is LessonPlan:
            parsed: BaseModel = self._plan()
        elif schema is JudgeVerdict:
            self.judge_calls += 1
            parsed = self._judge(prompt)
        elif schema is ReflectionOutput:
            parsed = self._reflect(prompt)
        else:  # pragma: no cover - defensive
            raise ProviderError(f"MockProvider has no script for schema {schema.__name__}")

        return StructuredCompletion(
            parsed=parsed, raw_text=parsed.model_dump_json(), usage=usage, model=f"mock:{model}"
        )

    # -------------------------------------------------------------- scripts

    def _plan(self) -> LessonPlan:
        return LessonPlan(
            topic="Introduction to RAG (Retrieval-Augmented Generation)",
            one_sentence_definition=(
                "RAG is a way to let an AI model look up real text before it answers, "
                "instead of answering only from memory."
            ),
            learning_objectives=[
                "Explain what RAG stands for and what each word does",
                "Describe the three problems RAG solves",
                "Walk through retrieve, augment, and generate for one question",
                "Explain why RAG is not the same as training the model",
                "Name two situations where RAG still gives a wrong answer",
            ],
            prerequisite_concepts=["large language model", "training data", "prompt"],
            concept_order=[
                "what a large language model is",
                "why it can be wrong or out of date",
                "the open-book exam analogy",
                "chunks",
                "embeddings",
                "vector database and index",
                "retrieve, augment, generate",
                "worked example",
                "RAG vs fine-tuning",
                "failure modes",
            ],
            analogy="An open-book exam versus a closed-book exam.",
            worked_example="How many casual leave days do I get, answered from a company handbook.",
            common_misconceptions=[
                "That RAG retrains or permanently updates the model",
                "That RAG removes all wrong answers",
                "That a vector database is compulsory",
            ],
            jargon_to_define=[
                "large language model", "hallucination", "chunk", "embedding",
                "vector database", "index", "prompt", "top-k", "fine-tuning",
            ],
        )

    def _judge(self, prompt: str) -> JudgeVerdict:
        """Evaluate the lesson embedded in the judge prompt against sentinels."""
        # Search the lesson only. The full prompt also carries the ground truth
        # and the rubric questions — and several questions quote the exact
        # phrases they forbid ("as we will see later"), so scanning the whole
        # prompt makes every check fail itself on every lesson.
        lesson = _extract_lesson(prompt)
        lowered = lesson.lower()
        results: list[JudgeCheck] = []

        for check_id, phrases in _FORBIDDEN_CLAIMS.items():
            hit = next((p for p in phrases if p in lowered), None)
            results.append(
                JudgeCheck(
                    check_id=check_id,
                    passed=hit is None,
                    reason="" if hit is None else f"The lesson contains the phrase '{hit}'.",
                    evidence=_excerpt(lesson, hit) if hit else "",
                )
            )

        for check_id, signals in _REQUIRED_ANY.items():
            hit = next((s for s in signals if s in lowered), None)
            results.append(
                JudgeCheck(
                    check_id=check_id,
                    passed=hit is not None,
                    reason="" if hit else f"No sign of the required element for {check_id}.",
                    evidence=_excerpt(lesson, hit) if hit else "",
                )
            )

        for check_id, signals in _REQUIRED_ALL.items():
            missing = [s for s in signals if s not in lowered]
            present = next((s for s in signals if s in lowered), None)
            results.append(
                JudgeCheck(
                    check_id=check_id,
                    passed=not missing,
                    reason=(
                        ""
                        if not missing
                        else f"The lesson is missing required elements for "
                             f"{check_id}: {', '.join(missing)}."
                    ),
                    evidence=_excerpt(lesson, present) if present else "",
                )
            )

        return JudgeVerdict(results=results)

    # Canned directives keyed by check, so the mock reflector responds to the
    # checks it was actually asked about rather than a hardcoded guess.
    _DIRECTIVES: dict[str, str] = {
        "sentence_length": "Write one idea per sentence and never exceed 25 words in a single sentence.",
        "readability_grade": "Prefer short everyday words over long formal ones; write for a reader using their second language.",
        "jargon_density": "Define every technical term in plain words in the same sentence where it first appears.",
        "jargon_defined_on_first_use": "Never use a technical term before you have defined it in plain words.",
        "no_idioms_or_cultural_refs": "Use literal wording only; never use idioms, slang, or sports and culture references.",
        "accuracy_grounded": "State only what the grounding source supports, and never claim a technique removes all errors.",
        "no_unsupported_claims": "Never invent statistics, benchmarks, dates, or company results; mark illustrative numbers as examples.",
        "no_weight_update_myth": "State explicitly that retrieved text goes into the prompt for one question only and the model never changes.",
        "has_concrete_analogy": "Open with one everyday analogy and map each part of it onto a part of the mechanism.",
        "has_worked_example": "Trace one specific question end to end, showing each stage as a separate labelled block.",
        "example_density": "Signpost every example and analogy explicitly with phrases like 'For example' or 'Think of it like'.",
        "covers_what_why_how": "Give what it is, why it matters, and how it works a full section each, not a passing sentence.",
        "covers_three_steps": "Name each pipeline stage using its actual word so the reader can connect it to the acronym.",
        "no_forward_references": "Never defer a definition the reader needs now; move the explanation earlier instead.",
        "standalone_completeness": "Never refer to other lessons, modules, videos, or links; inline everything the reader needs.",
    }

    def _reflect(self, prompt: str) -> ReflectionOutput:
        """Respond to the check ids actually present in the prompt.

        A mock that always proposes the same patch would pass a test that a real
        reflector fails, because the real one is constrained to the checks it was
        asked about. Parsing the prompt keeps the mock honest about that contract.
        """
        import re

        asked = re.findall(r"check_id:\s*(\w+)", prompt)
        patches = [
            PatchProposal(
                check_id=cid,
                directive=self._DIRECTIVES[cid],
                rationale=f"{cid} failed repeatedly; preventing it up front is cheaper than fixing it on retry.",
            )
            for cid in asked
            if cid in self._DIRECTIVES
        ]
        return ReflectionOutput(patches=patches[:3])


def _extract_lesson(prompt: str) -> str:
    """Pull the lesson out of the judge prompt's <lesson> block."""
    start = prompt.find("<lesson>")
    end = prompt.rfind("</lesson>")
    if start == -1 or end == -1 or end <= start:
        return prompt
    return prompt[start + len("<lesson>") : end]


def _excerpt(text: str, needle: str | None, width: int = 90) -> str:
    if not needle:
        return ""
    idx = text.lower().find(needle)
    if idx < 0:
        return ""
    start = max(0, idx - width // 2)
    return text[start : idx + len(needle) + width // 2].replace("\n", " ").strip()
