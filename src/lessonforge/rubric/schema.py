"""Rubric data model.

Design rule: **no partial credit anywhere**. A check is PASS or FAIL. There is
no 0-10 score, no weighted average, no "mostly passes". This is deliberate —
a numeric score invites a threshold argument ("is 7.5 good enough?") and lets a
model talk its way to a pass. A boolean forces the evaluator to commit.

The overall verdict is a plain AND across every blocking check.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Dimension(str, Enum):
    """The six quality dimensions from the brief."""

    ACCURATE_GROUNDED = "accurate_grounded"
    BEGINNER_LANGUAGE = "beginner_language"
    TEACHES_BY_EXAMPLE = "teaches_by_example"
    NO_UNEXPLAINED_JARGON = "no_unexplained_jargon"
    COVERS_KEY_POINTS = "covers_key_points"
    COHERENT_FLOW = "coherent_flow"


class CheckKind(str, Enum):
    """How a check is executed.

    DETERMINISTIC checks are pure Python: same input, same result, no API call,
    no cost, no way for the generator to argue with them.

    JUDGED checks need semantic understanding and are delegated to an LLM in a
    fresh context that never sees the generation prompt.
    """

    DETERMINISTIC = "deterministic"
    JUDGED = "judged"


class CheckSpec(BaseModel):
    """Definition of a single rubric checkpoint."""

    id: str
    dimension: Dimension
    kind: CheckKind
    blocking: bool = True
    title: str
    # Written as a yes/no question so the judge cannot hedge.
    question: str
    # Shown to the generator on retry so it knows what "fixed" looks like.
    remediation_hint: str

    model_config = {"frozen": True}


class CheckResult(BaseModel):
    """Outcome of one check against one lesson draft."""

    check_id: str
    passed: bool
    # Why it failed. Required on failure, ignored on pass. This string is what
    # gets fed back into the regeneration prompt, so it must be actionable.
    reason: str = ""
    # A verbatim quote from the lesson that proves the verdict. Forcing the
    # judge to cite text is the single most effective anti-hallucination
    # measure in the evaluator — it cannot invent a violation it can't quote.
    evidence: str = ""
    kind: CheckKind = CheckKind.JUDGED
    blocking: bool = True

    @property
    def status(self) -> Literal["PASS", "FAIL"]:
        return "PASS" if self.passed else "FAIL"


class JudgeCheck(BaseModel):
    """One verdict as returned by the judge.

    Deliberately narrower than `CheckResult`: the judge reports *what it found*
    and nothing else. Whether a check is blocking, and which engine ran it, are
    facts about the rubric, not opinions the judge is entitled to. Those fields
    are filled in from the registry after the call, so a judge cannot downgrade
    a blocking check to advisory to make a lesson pass.
    """

    check_id: str = Field(description="Exact id of the check being answered.")
    passed: bool = Field(description="true if the lesson satisfies the check, else false.")
    reason: str = Field(
        default="",
        description="If failed: what is wrong and what to change. Empty when passed.",
    )
    evidence: str = Field(
        default="",
        description="Verbatim quote from the lesson proving the verdict. Required when failed.",
    )


class JudgeVerdict(BaseModel):
    """Structured output contract for the LLM judge.

    Handed to Gemini as a response schema, so the judge physically cannot return
    prose instead of verdicts.
    """

    results: list[JudgeCheck] = Field(default_factory=list)


class Evaluation(BaseModel):
    """Full evaluation of one draft: deterministic + judged, merged."""

    attempt: int
    results: list[CheckResult] = Field(default_factory=list)

    @property
    def blocking_failures(self) -> list[CheckResult]:
        return [r for r in self.results if r.blocking and not r.passed]

    @property
    def advisory_failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.blocking and not r.passed]

    @property
    def passed(self) -> bool:
        """Ship gate: every blocking check must pass. Plain AND, no averaging."""
        return len(self.blocking_failures) == 0

    @property
    def summary(self) -> str:
        total = len(self.results)
        ok = sum(1 for r in self.results if r.passed)
        return f"{ok}/{total} checks passed"

    def by_id(self, check_id: str) -> CheckResult | None:
        for r in self.results:
            if r.check_id == check_id:
                return r
        return None
