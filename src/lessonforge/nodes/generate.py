"""Generator node: plan (+ prior failures) -> lesson markdown.

On attempt 1 the generator sees the plan and any learned directives from memory.
On attempts 2 and 3 it additionally sees a structured account of exactly which
checks failed, why, and the quoted offending text. That specificity matters:
"make it simpler" produces a differently-bad lesson, while "this 44-word
sentence uses four undefined terms" produces a fix.
"""

from __future__ import annotations

import json

from ..config import Settings
from ..inject import apply_injection
from ..llm.base import LLMProvider, ProviderError
from ..rubric.registry import BY_ID
from ..state import ForgeState


def _render_plan(plan) -> str:
    if plan is None:
        return "(no plan available)"
    return json.dumps(plan.model_dump(), indent=2, ensure_ascii=False)


def build_feedback(evaluation) -> str:
    """Turn the last evaluation into a revision brief.

    Only failures appear. Listing what passed invites the model to rewrite
    things that were already fine and regress them.
    """
    if evaluation is None:
        return ""

    failures = evaluation.blocking_failures
    if not failures:
        return ""

    lines = [
        "## Revision required",
        "",
        f"Your previous draft failed {len(failures)} blocking check(s). "
        "Fix every one. Keep everything that was not flagged — do not rewrite "
        "the whole lesson from scratch.",
        "",
    ]

    for i, result in enumerate(failures, start=1):
        spec = BY_ID.get(result.check_id)
        lines.append(f"### {i}. {spec.title if spec else result.check_id}")
        lines.append(f"- **Check:** `{result.check_id}`")
        lines.append(f"- **Why it failed:** {result.reason}")
        if result.evidence:
            evidence = result.evidence.strip().replace("\n", " ")
            lines.append(f"- **Offending text:** \"{evidence[:400]}\"")
        if spec:
            lines.append(f"- **How to fix it:** {spec.remediation_hint}")
        lines.append("")

    advisory = evaluation.advisory_failures
    if advisory:
        notes = ", ".join(f"{a.check_id} ({a.reason})" for a in advisory)
        lines.append(f"_Advisory, not blocking: {notes}_")
        lines.append("")

    return "\n".join(lines)


def generate_node(
    state: ForgeState, *, provider: LLMProvider, settings: Settings
) -> dict:
    attempt = state.get("attempt", 0) + 1

    evaluations = state.get("evaluations") or []
    feedback = build_feedback(evaluations[-1]) if evaluations else ""

    prompt = (
        settings.prompt("generator")
        .replace("{{GROUND_TRUTH}}", settings.ground_truth())
        .replace("{{PLAN}}", _render_plan(state.get("plan")))
        .replace("{{PATCHES}}", state.get("patch_block", ""))
        .replace("{{FEEDBACK}}", feedback)
    )

    try:
        completion = provider.complete(
            model=settings.generator_model,
            prompt=prompt,
            temperature=settings.generator_temperature,
            max_output_tokens=settings.max_output_tokens,
        )
    except ProviderError as exc:
        return {
            "attempt": attempt,
            "error": f"Generator failed on attempt {attempt}: {exc}",
            "events": [
                {"node": "generate", "attempt": attempt, "status": "error", "detail": str(exc)}
            ],
        }

    lesson = completion.text.strip()
    events = [
        {
            "node": "generate",
            "attempt": attempt,
            "status": "ok",
            "chars": len(lesson),
            "had_feedback": bool(feedback),
        }
    ]

    # Error injection sits between generation and evaluation so the evaluator is
    # tested against a lesson that was genuinely good a moment ago. Injecting
    # only on attempt 1 lets the loop demonstrate recovery on attempt 2.
    inject = state.get("inject_error")
    if inject and attempt == 1:
        lesson, expected, described = apply_injection(lesson, inject)
        events.append(
            {
                "node": "inject",
                "attempt": attempt,
                "status": "injected",
                "mode": inject,
                "expected_failures": expected,
                "detail": described,
            }
        )

    return {
        "attempt": attempt,
        "lesson": lesson,
        "drafts": [lesson],
        "feedback": feedback,
        "usage": completion.usage,
        "events": events,
    }
