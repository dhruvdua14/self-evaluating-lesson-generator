"""The rubric: definitions, both check engines, and the evaluator."""

from .deterministic import analyse, run_deterministic_checks
from .judge import evaluate, judge_lesson
from .registry import BLOCKING_IDS, BY_ID, DETERMINISTIC_CHECKS, JUDGED_CHECKS, RUBRIC, spec
from .schema import (
    CheckKind,
    CheckResult,
    CheckSpec,
    Dimension,
    Evaluation,
    JudgeCheck,
    JudgeVerdict,
)

__all__ = [
    "BLOCKING_IDS",
    "BY_ID",
    "DETERMINISTIC_CHECKS",
    "JUDGED_CHECKS",
    "RUBRIC",
    "CheckKind",
    "CheckResult",
    "CheckSpec",
    "Dimension",
    "Evaluation",
    "JudgeCheck",
    "JudgeVerdict",
    "analyse",
    "evaluate",
    "judge_lesson",
    "run_deterministic_checks",
    "spec",
]
