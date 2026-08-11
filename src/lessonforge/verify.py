"""Evaluator verification: does the rubric actually catch planted errors?

This is the answer to the obvious challenge — "your evaluator passed the lesson,
but how do you know it would have failed a bad one?"

The procedure is a controlled experiment:

1. Take a baseline lesson that passes every blocking check. Confirm it does.
   If the baseline does not pass, the experiment is void and says so.
2. Corrupt a copy in one specific, known way.
3. Predict which checks must now fail — stated up front in `inject.py`, not
   after seeing the result.
4. Run the evaluator and compare.

A caught injection proves the check discriminates. A missed injection is a hole
in the rubric, reported as such rather than quietly ignored. Either way the
result is a fact about the evaluator rather than an opinion about it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .inject import INJECTIONS, apply_injection
from .llm.base import LLMProvider
from .rubric.judge import evaluate


@dataclass
class InjectionOutcome:
    mode: str
    description: str
    expected: list[str]
    actually_failed: list[str]
    # Checks that did not really run — the evaluator errored or was rate
    # limited. Tracked separately because a failed API call is not evidence
    # that a planted error was caught.
    errored: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errored is None:
            self.errored = []

    @property
    def caught(self) -> list[str]:
        """Predicted checks that failed *on the content*, not on an API error."""
        genuine = set(self.actually_failed) - set(self.errored)
        return sorted(set(self.expected) & genuine)

    @property
    def missed(self) -> list[str]:
        genuine = set(self.actually_failed) - set(self.errored)
        return sorted(set(self.expected) - genuine)

    @property
    def inconclusive(self) -> bool:
        """A predicted check that never actually ran proves nothing either way."""
        return bool(set(self.expected) & set(self.errored))

    @property
    def collateral(self) -> list[str]:
        """Checks that failed but were not predicted.

        Not necessarily wrong — a corrupted lesson often trips genuinely related
        checks. Reported so a human can judge whether the rubric is over-firing.
        """
        return sorted(set(self.actually_failed) - set(self.expected))

    @property
    def passed(self) -> bool:
        return not self.missed


@dataclass
class VerificationReport:
    baseline_passed: bool
    baseline_failures: list[str]
    outcomes: list[InjectionOutcome]
    baseline_errored: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.baseline_errored is None:
            self.baseline_errored = []

    @property
    def valid(self) -> bool:
        """The experiment is only meaningful if the baseline genuinely passed.

        Two ways it can be void: the baseline was already failing, or the
        evaluator never actually ran. The second is the dangerous one — when
        every judge call errors, every check "fails" for every input, and each
        planted error looks trivially caught. That failure mode produced a
        confident green result on a run where the evaluator was rate limited,
        which is precisely the kind of false confidence this whole system
        exists to prevent.
        """
        return self.baseline_passed and not self.baseline_errored

    @property
    def any_errored(self) -> bool:
        return bool(self.baseline_errored) or any(o.errored for o in self.outcomes)

    @property
    def all_caught(self) -> bool:
        return (
            self.valid
            and not self.any_errored
            and all(o.passed for o in self.outcomes)
        )


DEFAULT_BASELINE = Path(__file__).parent / "llm" / "fixtures" / "draft_good.md"


def verify_evaluator(
    *,
    provider: LLMProvider,
    settings: Settings,
    baseline: str | None = None,
    modes: list[str] | None = None,
    on_progress=None,
) -> VerificationReport:
    lesson = baseline if baseline is not None else DEFAULT_BASELINE.read_text(encoding="utf-8")
    selected = modes or list(INJECTIONS.keys())

    def progress(stage: str, detail: str = "") -> None:
        if on_progress:
            on_progress(stage, detail)

    progress("baseline", "evaluating clean lesson")
    base_eval, _ = evaluate(lesson=lesson, attempt=0, provider=provider, settings=settings)
    baseline_failures = [r.check_id for r in base_eval.blocking_failures]
    baseline_errored = [r.check_id for r in base_eval.results if r.errored]

    outcomes: list[InjectionOutcome] = []
    for mode in selected:
        inj = INJECTIONS[mode]
        progress("inject", mode)
        corrupted, expected, _ = apply_injection(lesson, mode)
        result, _ = evaluate(
            lesson=corrupted, attempt=0, provider=provider, settings=settings
        )
        outcomes.append(
            InjectionOutcome(
                mode=mode,
                description=inj.description,
                expected=expected,
                actually_failed=[r.check_id for r in result.blocking_failures],
                errored=[r.check_id for r in result.results if r.errored],
            )
        )

    return VerificationReport(
        baseline_passed=base_eval.passed,
        baseline_failures=baseline_failures,
        baseline_errored=baseline_errored,
        outcomes=outcomes,
    )
