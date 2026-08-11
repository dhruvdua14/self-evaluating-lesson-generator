"""Standing regression test on the rubric itself.

If someone loosens a check, weakens a threshold, or edits a prompt in a way that
stops a planted error from being caught, one of these fails. That is the point:
the rubric is the product here, so the rubric needs tests.
"""

from __future__ import annotations

import pytest

from lessonforge.inject import ALL_MODES, INJECTIONS, apply_injection
from lessonforge.rubric.judge import evaluate
from lessonforge.rubric.registry import BY_ID
from lessonforge.verify import verify_evaluator


def test_every_injection_predicts_real_check_ids():
    """A prediction naming a nonexistent check would silently never fail."""
    for injection in INJECTIONS.values():
        for check_id in injection.expects_failure_of:
            assert check_id in BY_ID, f"{injection.mode} predicts unknown check {check_id}"


def test_every_predicted_check_is_blocking():
    """Predicting an advisory check would prove nothing about shipping."""
    for injection in INJECTIONS.values():
        for check_id in injection.expects_failure_of:
            assert BY_ID[check_id].blocking, (
                f"{injection.mode} predicts advisory check {check_id}"
            )


def test_baseline_lesson_passes_before_any_injection(settings, provider, good_lesson):
    """The experiment is only meaningful from a clean starting point."""
    evaluation, _ = evaluate(
        lesson=good_lesson, attempt=0, provider=provider, settings=settings
    )
    failures = [r.check_id for r in evaluation.blocking_failures]
    assert failures == [], f"baseline must be clean, failed: {failures}"


@pytest.mark.parametrize("mode", sorted(INJECTIONS))
def test_injection_is_caught_by_its_predicted_checks(mode, settings, provider, good_lesson):
    corrupted, expected, _ = apply_injection(good_lesson, mode)
    evaluation, _ = evaluate(
        lesson=corrupted, attempt=0, provider=provider, settings=settings
    )
    failed = {r.check_id for r in evaluation.blocking_failures}

    missed = sorted(set(expected) - failed)
    assert not missed, f"injection '{mode}' was not caught by: {missed}"
    assert not evaluation.passed, f"corrupted lesson '{mode}' should never ship"


def test_injection_actually_changes_the_lesson(good_lesson):
    for mode in INJECTIONS:
        corrupted, _, _ = apply_injection(good_lesson, mode)
        assert corrupted != good_lesson, f"injection '{mode}' was a no-op"


def test_all_mode_applies_every_injection(good_lesson):
    corrupted, expected, described = apply_injection(good_lesson, "all")
    assert len(described) == len(INJECTIONS)
    for injection in INJECTIONS.values():
        for check_id in injection.expects_failure_of:
            assert check_id in expected


def test_unknown_mode_raises(good_lesson):
    with pytest.raises(ValueError):
        apply_injection(good_lesson, "definitely-not-a-mode")


def test_all_modes_are_listed():
    assert set(ALL_MODES) == set(INJECTIONS) | {"all"}


def test_verify_reports_a_clean_rubric(settings, provider):
    """The whole verification run, as the CLI executes it."""
    report = verify_evaluator(provider=provider, settings=settings)
    assert report.valid, f"baseline failed: {report.baseline_failures}"
    assert report.all_caught, [
        (o.mode, o.missed) for o in report.outcomes if o.missed
    ]


def test_verify_flags_an_invalid_experiment(settings, provider, bad_lesson):
    """Verifying against an already-failing baseline must be reported, not hidden."""
    report = verify_evaluator(provider=provider, settings=settings, baseline=bad_lesson)
    assert not report.valid
    assert not report.all_caught


def test_rate_limited_evaluator_never_reports_success(settings):
    """Regression: an outage used to look like a perfectly working rubric.

    A live verification run reported "every planted error was caught" while the
    judge was returning 429 for every call. With no evaluator running, every
    check fails for every input, so each planted error is trivially "caught" —
    a confidently green result on an experiment that never happened. An
    evaluator failure must void the run, not decorate it.
    """

    class RateLimitedProvider:
        name = "ratelimited"

        def complete(self, **kwargs):  # pragma: no cover - unused
            raise AssertionError

        def complete_structured(self, **kwargs):
            from lessonforge.llm.base import ProviderError

            raise ProviderError("429 RESOURCE_EXHAUSTED: quota exceeded")

    report = verify_evaluator(provider=RateLimitedProvider(), settings=settings)

    assert not report.valid, "a run where the judge never answered must be void"
    assert not report.all_caught, "must never claim success on an evaluator outage"
    assert report.any_errored
    assert report.baseline_errored


def test_errored_checks_are_not_counted_as_catches(settings):
    """An API failure is not evidence that a planted error was caught."""
    from lessonforge.verify import InjectionOutcome

    outcome = InjectionOutcome(
        mode="factual",
        description="",
        expected=["no_weight_update_myth"],
        actually_failed=["no_weight_update_myth"],
        errored=["no_weight_update_myth"],
    )
    assert outcome.caught == []
    assert outcome.missed == ["no_weight_update_myth"]
    assert outcome.inconclusive


def test_backoff_outlasts_a_rate_limit_window():
    """A 429 needs a minute-scale wait, not the 8s ceiling used for 5xx."""
    from lessonforge.llm.gemini import _backoff_seconds

    rate_limited = Exception("429 RESOURCE_EXHAUSTED quota exceeded")
    assert _backoff_seconds(rate_limited, 0) >= 30
    assert _backoff_seconds(rate_limited, 1) >= 60

    # Server-supplied delay wins over any guess.
    assert _backoff_seconds(Exception("{'retryDelay': '38s'}"), 0) == 40

    # Ordinary transient errors keep short backoff.
    assert _backoff_seconds(Exception("503 UNAVAILABLE"), 0) <= 2
