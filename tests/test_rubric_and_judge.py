"""Rubric integrity and evaluator anti-gaming defences."""

from __future__ import annotations

import pytest

from lessonforge.rubric.judge import _evidence_is_real, evaluate
from lessonforge.rubric.registry import BLOCKING_IDS, BY_ID, JUDGED_CHECKS, RUBRIC
from lessonforge.rubric.schema import CheckKind, CheckResult, Evaluation


# ------------------------------------------------------------ rubric shape


def test_check_ids_are_unique():
    ids = [c.id for c in RUBRIC]
    assert len(ids) == len(set(ids))


def test_every_check_has_a_question_and_remediation():
    for spec in RUBRIC:
        assert spec.question.strip(), f"{spec.id} has no question"
        assert spec.remediation_hint.strip(), f"{spec.id} has no remediation hint"


def test_all_six_dimensions_are_covered():
    from lessonforge.rubric.schema import Dimension

    covered = {c.dimension for c in RUBRIC}
    assert covered == set(Dimension), f"uncovered dimensions: {set(Dimension) - covered}"


def test_rubric_has_both_engines():
    kinds = {c.kind for c in RUBRIC}
    assert kinds == {CheckKind.DETERMINISTIC, CheckKind.JUDGED}


def test_most_checks_are_blocking():
    """Advisory checks are the exception; a mostly-advisory rubric is a rubber stamp."""
    assert len(BLOCKING_IDS) >= len(RUBRIC) - 3


# --------------------------------------------------------- pass/fail algebra


def _res(check_id: str, passed: bool, blocking: bool = True) -> CheckResult:
    return CheckResult(check_id=check_id, passed=passed, blocking=blocking)


def test_evaluation_passes_only_when_all_blocking_checks_pass():
    assert Evaluation(attempt=1, results=[_res("a", True), _res("b", True)]).passed
    assert not Evaluation(attempt=1, results=[_res("a", True), _res("b", False)]).passed


def test_advisory_failure_does_not_block_shipping():
    ev = Evaluation(attempt=1, results=[_res("a", True), _res("b", False, blocking=False)])
    assert ev.passed
    assert len(ev.advisory_failures) == 1


def test_no_partial_credit_exists_in_the_model():
    """There must be no numeric score anywhere — scores invite threshold arguments."""
    fields = set(CheckResult.model_fields)
    for banned in ("score", "rating", "confidence", "weight", "points"):
        assert banned not in fields


# ------------------------------------------------- fabricated evidence guard


def test_real_quote_is_accepted():
    lesson = "An embedding is a list of numbers that represents meaning."
    assert _evidence_is_real("a list of numbers that represents meaning", lesson)


def test_reflowed_quote_is_accepted():
    """Models re-wrap whitespace when quoting; that must not count as fabrication."""
    lesson = "An embedding is a list\nof numbers that\nrepresents meaning."
    assert _evidence_is_real("An embedding is a list of numbers that represents meaning.", lesson)


def test_fabricated_quote_is_rejected():
    lesson = "An embedding is a list of numbers that represents meaning."
    assert not _evidence_is_real(
        "RAG permanently retrains the model on all of your private documents", lesson
    )


def test_failure_with_fabricated_evidence_is_downgraded_to_pass(settings, good_lesson):
    """A judge cannot fail a lesson using a quote that is not in it."""

    class FabricatingProvider:
        name = "fabricator"

        def complete(self, **kwargs):  # pragma: no cover - unused
            raise AssertionError

        def complete_structured(self, *, schema, **kwargs):
            from lessonforge.llm.base import StructuredCompletion, Usage
            from lessonforge.rubric.schema import JudgeCheck

            verdict = schema(
                results=[
                    JudgeCheck(
                        check_id=spec.id,
                        passed=False,
                        reason="Invented problem.",
                        evidence="This sentence appears nowhere in the lesson whatsoever.",
                    )
                    for spec in JUDGED_CHECKS
                ]
            )
            return StructuredCompletion(parsed=verdict, usage=Usage(calls=1))

    evaluation, _ = evaluate(
        lesson=good_lesson, attempt=1, provider=FabricatingProvider(), settings=settings
    )
    judged = [r for r in evaluation.results if r.kind is CheckKind.JUDGED]
    assert judged, "expected judged results"
    assert all(r.passed for r in judged), "fabricated failures should be rejected"
    assert any("evidence rejected" in r.evidence for r in judged)


# ---------------------------------------------------- silence is not a pass


def test_missing_verdict_is_treated_as_failure(settings, good_lesson):
    """A judge that omits a check must not thereby grant it a pass."""

    class SilentProvider:
        name = "silent"

        def complete(self, **kwargs):  # pragma: no cover - unused
            raise AssertionError

        def complete_structured(self, *, schema, **kwargs):
            from lessonforge.llm.base import StructuredCompletion, Usage

            return StructuredCompletion(parsed=schema(results=[]), usage=Usage(calls=1))

    evaluation, _ = evaluate(
        lesson=good_lesson, attempt=1, provider=SilentProvider(), settings=settings
    )
    judged = [r for r in evaluation.results if r.kind is CheckKind.JUDGED]
    assert all(not r.passed for r in judged)
    assert not evaluation.passed


def test_judge_failure_fails_closed(settings, good_lesson):
    """If the evaluator errors, nothing ships."""

    class BrokenProvider:
        name = "broken"

        def complete(self, **kwargs):  # pragma: no cover - unused
            raise AssertionError

        def complete_structured(self, **kwargs):
            from lessonforge.llm.base import ProviderError

            raise ProviderError("judge exploded")

    evaluation, _ = evaluate(
        lesson=good_lesson, attempt=1, provider=BrokenProvider(), settings=settings
    )
    assert not evaluation.passed


def test_judge_cannot_downgrade_a_blocking_check(settings, good_lesson):
    """Blocking status comes from the registry, never from the model."""

    class LiarProvider:
        name = "liar"

        def complete(self, **kwargs):  # pragma: no cover - unused
            raise AssertionError

        def complete_structured(self, *, schema, **kwargs):
            from lessonforge.llm.base import StructuredCompletion, Usage
            from lessonforge.rubric.schema import JudgeCheck

            return StructuredCompletion(
                parsed=schema(
                    results=[
                        JudgeCheck(check_id=s.id, passed=False, reason="x", evidence="")
                        for s in JUDGED_CHECKS
                    ]
                ),
                usage=Usage(calls=1),
            )

    evaluation, _ = evaluate(
        lesson=good_lesson, attempt=1, provider=LiarProvider(), settings=settings
    )
    for result in evaluation.results:
        if result.kind is CheckKind.JUDGED:
            assert result.blocking == BY_ID[result.check_id].blocking
