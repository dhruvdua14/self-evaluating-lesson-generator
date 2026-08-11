"""Evaluator node: lesson -> pass/fail per checkpoint.

This node decides whether the content ships. It runs the deterministic checks
locally and the judged checks through an isolated LLM call, then merges both
into one Evaluation whose `passed` property is a plain AND over blocking checks.
"""

from __future__ import annotations

from ..config import Settings
from ..llm.base import LLMProvider
from ..memory import MemoryStore
from ..rubric.deterministic import analyse
from ..rubric.judge import evaluate as run_evaluation
from ..state import ForgeState


def evaluate_node(
    state: ForgeState, *, provider: LLMProvider, settings: Settings, store: MemoryStore
) -> dict:
    lesson = state.get("lesson", "")
    attempt = state.get("attempt", 1)

    if not lesson.strip():
        detail = "Nothing to evaluate: the generator produced an empty lesson."
        return {
            "error": detail,
            "events": [
                {"node": "evaluate", "attempt": attempt, "status": "error", "detail": detail}
            ],
        }

    evaluation, usage = run_evaluation(
        lesson=lesson, attempt=attempt, provider=provider, settings=settings
    )

    stats = analyse(lesson, settings.readability.long_sentence_words)

    run_id = state.get("run_id")
    if run_id is not None:
        store.record_evaluation(run_id, evaluation, stats.word_count)

    failed_ids = [r.check_id for r in evaluation.blocking_failures]

    return {
        "evaluations": [evaluation],
        "usage": usage,
        "events": [
            {
                "node": "evaluate",
                "attempt": attempt,
                "status": "pass" if evaluation.passed else "fail",
                "summary": evaluation.summary,
                "failed": failed_ids,
                "grade_level": stats.flesch_kincaid_grade,
                "word_count": stats.word_count,
            }
        ],
    }
