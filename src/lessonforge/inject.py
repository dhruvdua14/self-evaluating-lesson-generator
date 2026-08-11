"""Deliberate error injection — the evaluator's own test suite.

An evaluator nobody has tried to fool is an evaluator nobody knows works. A
rubric that always passes and a rubric that is never violated look identical
from the outside.

This module corrupts a *passing* lesson in known, specific ways after generation
and before evaluation. Each injection names the check it should trip, so the
result is a falsifiable claim: plant this error, and that check must fail. If it
does not, the rubric has a hole and the run says so.

Used two ways:

* `--inject-error <mode>` for a live demonstration.
* `pytest tests/test_inject.py` as a standing regression test on the rubric.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Injection:
    mode: str
    description: str
    expects_failure_of: tuple[str, ...]
    payload: str


INJECTIONS: dict[str, Injection] = {
    "factual": Injection(
        mode="factual",
        description=(
            "Plants the single most common beginner misconception: that RAG "
            "retrains the model and stores documents in its weights."
        ),
        expects_failure_of=("no_weight_update_myth", "accuracy_grounded"),
        payload=(
            "\n\n## How the model stores your documents\n\n"
            "When you run RAG, the model is fine-tuned on your documents. "
            "It permanently absorbs that knowledge into its weights. "
            "After indexing, your documents become part of the model itself, "
            "so they no longer need to be supplied at question time. "
            "This is why RAG completely eliminates hallucination and guarantees "
            "that every answer is factually correct.\n"
        ),
    ),
    "fabrication": Injection(
        mode="fabrication",
        description="Plants invented statistics presented as established fact.",
        expects_failure_of=("no_unsupported_claims",),
        payload=(
            "\n\n## Measured results\n\n"
            "Teams that deploy RAG see a 47% reduction in factual errors and a "
            "3.2x improvement in user satisfaction within the first quarter, "
            "according to a 2024 benchmark across 1,850 production systems. "
            "Google reported in March 2023 that RAG cut its support costs by "
            "62 crore rupees annually.\n"
        ),
    ),
    "jargon": Injection(
        mode="jargon",
        description=(
            "Plants a dense, undefined-jargon sentence that should trip both the "
            "deterministic readability gates and the judged jargon check."
        ),
        # Deliberately does NOT predict `readability_grade` or `sentence_length`.
        # Verification showed one dense paragraph appended to a long clean lesson
        # moves those document-level averages only 4.67 -> 5.62 — correctly
        # inside the limit. `no_runaway_sentence` exists precisely to catch the
        # localised damage that averaging hides.
        # `jargon_density` was demoted to advisory (see registry.py), and a
        # prediction naming an advisory check proves nothing about shipping.
        expects_failure_of=("jargon_defined_on_first_use", "no_runaway_sentence"),
        payload=(
            "\n\n## Technical addendum\n\n"
            "The retrieval subsystem computes dense vector embeddings through a "
            "bi-encoder architecture and persists them within a specialised vector "
            "database supporting approximate nearest-neighbour traversal across "
            "high-dimensional latent manifolds, whereupon the inference pipeline "
            "executes a top-k cosine similarity lookup in order to surface the "
            "most semantically proximate passages from the indexed corpus while "
            "remaining within acceptable latency budgets for interactive "
            "workloads.\n"
        ),
    ),
    "idiom": Injection(
        mode="idiom",
        description=(
            "Plants English idioms and Western cultural references that the "
            "target learner would not understand."
        ),
        expects_failure_of=("no_idioms_or_cultural_refs",),
        payload=(
            "\n\n## The bottom line\n\n"
            "At the end of the day, RAG is not a silver bullet, but for most "
            "teams it is a home run. You can get it working out of the box, and "
            "once you do, it is a piece of cake. Ballpark, you are looking at a "
            "slam dunk for any team that wants to hit it out of the park with "
            "their documents.\n"
        ),
    ),
    "dependency": Injection(
        mode="dependency",
        description=(
            "Breaks self-containment by referring to earlier lessons and "
            "deferring a definition the reader needs immediately."
        ),
        expects_failure_of=("standalone_completeness", "no_forward_references"),
        payload=(
            "\n\n## Further notes\n\n"
            "Recall from the previous module that latency budgets constrain the "
            "top-k parameter. As we saw in the last lesson, the embedding model "
            "matters here. We will explain what an embedding actually is later "
            "in this course, but for now just apply the rule from Module 2 and "
            "watch the accompanying video before continuing.\n"
        ),
    ),
    "coverage": Injection(
        mode="coverage",
        description=(
            "Deletes the traced worked example and the step-by-step section, "
            "leaving the lesson to describe RAG without ever walking one "
            "question through it."
        ),
        # Deliberately does NOT predict `covers_what_why_how`. It originally
        # did, and the live judge refused to fail it — correctly. Removing the
        # "How it works" *section* does not remove how-it-works *content*: the
        # analogy section and the recap still explain retrieve, augment, and
        # generate. The judge was reading for substance while the prediction was
        # reasoning about headings. See the `gutted` mode below for the
        # injection that genuinely removes coverage.
        expects_failure_of=("has_worked_example",),
        payload="",
    ),
    "gutted": Injection(
        mode="gutted",
        description=(
            "Keeps only the opening section, so nothing about how RAG works "
            "survives anywhere in the lesson."
        ),
        expects_failure_of=(
            "covers_what_why_how", "has_worked_example", "covers_three_steps",
        ),
        payload="",
    ),
}

ALL_MODES = tuple(INJECTIONS.keys()) + ("all",)


_SECTION_SPLIT = re.compile(r"^##\s+", re.MULTILINE)
_EXAMPLE_HEADING = re.compile(
    r"(worked example|example|step by step|how it works|walk ?through)", re.IGNORECASE
)


def _strip_teaching_sections(lesson: str) -> str:
    """Remove the sections that carry the actual instruction."""
    parts = _SECTION_SPLIT.split(lesson)
    if len(parts) <= 1:
        return lesson
    head, sections = parts[0], parts[1:]
    kept = [s for s in sections if not _EXAMPLE_HEADING.search(s.split("\n", 1)[0])]
    if len(kept) == len(sections):  # nothing matched; drop the middle instead
        kept = sections[:1] + sections[-1:]
    return head + "".join("## " + s for s in kept)


def _keep_only_opening(lesson: str) -> str:
    """Keep the title and the first H2 section only.

    Unlike `_strip_teaching_sections`, which removes sections by heading, this
    removes the body of the lesson outright — so no explanation of the pipeline
    survives anywhere, in a heading, an analogy, or a recap.
    """
    parts = _SECTION_SPLIT.split(lesson)
    if len(parts) <= 1:
        return lesson
    return parts[0] + "## " + parts[1]


def apply_injection(lesson: str, mode: str) -> tuple[str, list[str], list[str]]:
    """Corrupt a lesson.

    Returns (corrupted_lesson, expected_failing_check_ids, descriptions).
    """
    if mode == "all":
        text = lesson
        expected: list[str] = []
        described: list[str] = []
        for inj in INJECTIONS.values():
            text, exp, desc = apply_injection(text, inj.mode)
            expected.extend(exp)
            described.extend(desc)
        return text, sorted(set(expected)), described

    inj = INJECTIONS.get(mode)
    if inj is None:
        raise ValueError(
            f"Unknown injection mode {mode!r}. Choose one of: {', '.join(ALL_MODES)}"
        )

    if inj.mode == "coverage":
        corrupted = _strip_teaching_sections(lesson)
    elif inj.mode == "gutted":
        corrupted = _keep_only_opening(lesson)
    else:
        corrupted = lesson.rstrip() + inj.payload

    return corrupted, list(inj.expects_failure_of), [f"{inj.mode}: {inj.description}"]


def describe_modes() -> str:
    lines = []
    for inj in INJECTIONS.values():
        lines.append(
            f"  {inj.mode:<12} {inj.description}\n"
            f"  {'':<12} should fail: {', '.join(inj.expects_failure_of)}"
        )
    lines.append(f"  {'all':<12} Apply every injection above at once.")
    return "\n".join(lines)
