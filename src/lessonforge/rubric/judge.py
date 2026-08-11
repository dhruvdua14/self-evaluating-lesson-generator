"""LLM-as-judge for the semantic half of the rubric.

Judge independence
------------------
The judge call is built from three inputs only: the lesson text, the ground
truth, and the check list. It never sees the generator's system prompt, the
plan, the previous failure feedback, or the fact that this is attempt 3.

That isolation is the point. A model shown "here is what you were asked to
write, and here is what you wrote" grades its own homework and grades it kindly.
Handing it an anonymous document and a checklist removes the authorship cue that
drives that bias.

Two further defences:

* **Structured output.** The judge returns schema-validated verdicts, so it
  cannot answer a checklist with an essay.
* **Evidence quotes.** Every failure must carry a verbatim quote from the
  lesson. A judge that has to cite text cannot invent a violation, and one that
  quotes text which does not appear is caught automatically below.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from ..config import Settings
from ..llm.base import LLMProvider, ProviderError
from .registry import BY_ID, JUDGED_CHECKS
from .schema import CheckKind, CheckResult, Evaluation, JudgeVerdict


def _render_checks() -> str:
    lines = []
    for c in JUDGED_CHECKS:
        lines.append(
            f"### {c.id}\n"
            f"- dimension: {c.dimension.value}\n"
            f"- what it tests: {c.title}\n"
            f"- question: {c.question}"
        )
    return "\n\n".join(lines)


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def _evidence_is_real(evidence: str, lesson: str, *, threshold: float = 0.82) -> bool:
    """Check that a quoted failure actually appears in the lesson.

    Exact containment first. Models routinely re-wrap whitespace or trim a
    trailing clause when quoting, so a near-match over a sliding window is
    accepted too — the goal is to catch fabrication, not to punish reformatting.
    """
    ev = _normalise(evidence)
    if len(ev) < 12:
        return True  # too short to verify meaningfully; not evidence of fabrication
    body = _normalise(lesson)
    if ev in body:
        return True

    window = len(ev)
    if window > len(body):
        return SequenceMatcher(None, ev, body).ratio() >= threshold
    step = max(1, window // 4)
    for start in range(0, len(body) - window + 1, step):
        if SequenceMatcher(None, ev, body[start : start + window]).ratio() >= threshold:
            return True
    return False


def judge_lesson(
    *,
    lesson: str,
    provider: LLMProvider,
    settings: Settings,
) -> tuple[list[CheckResult], object]:
    """Run every judged check. Returns (results, usage)."""
    prompt = (
        settings.prompt("judge")
        .replace("{{GROUND_TRUTH}}", settings.ground_truth())
        .replace("{{CHECKS}}", _render_checks())
        .replace("{{LESSON}}", lesson)
    )

    completion = provider.complete_structured(
        model=settings.judge_model,
        prompt=prompt,
        schema=JudgeVerdict,
        temperature=settings.judge_temperature,
        max_output_tokens=settings.max_output_tokens,
    )
    verdict: JudgeVerdict = completion.parsed

    returned = {r.check_id: r for r in verdict.results}
    results: list[CheckResult] = []

    for spec in JUDGED_CHECKS:
        raw = returned.get(spec.id)

        if raw is None:
            # A check the judge declined to answer is a failure, never a pass.
            # Silence must never be a route to shipping.
            results.append(
                CheckResult(
                    check_id=spec.id,
                    passed=False,
                    reason=(
                        "The evaluator did not return a verdict for this check. "
                        "Treated as a failure so an unanswered check can never "
                        "become an implicit pass."
                    ),
                    evidence="",
                    kind=CheckKind.JUDGED,
                    blocking=spec.blocking,
                )
            )
            continue

        passed = bool(raw.passed)
        reason = (raw.reason or "").strip()
        evidence = (raw.evidence or "").strip()

        # Fabricated-evidence guard: a failure justified by a quote that is not
        # in the lesson is downgraded to a pass, with the discrepancy recorded.
        if not passed and evidence and not _evidence_is_real(evidence, lesson):
            passed = True
            reason = ""
            evidence = f"[evidence rejected: quote not found in lesson] {evidence[:160]}"

        if not passed and not reason:
            reason = f"Failed: {spec.title}. {spec.remediation_hint}"

        results.append(
            CheckResult(
                check_id=spec.id,
                passed=passed,
                reason=reason,
                evidence=evidence,
                # Authority for these two comes from the registry, not the model.
                kind=CheckKind.JUDGED,
                blocking=spec.blocking,
            )
        )

    return results, completion.usage


def evaluate(
    *,
    lesson: str,
    attempt: int,
    provider: LLMProvider,
    settings: Settings,
) -> tuple[Evaluation, object]:
    """Full evaluation: deterministic checks first, then the judge.

    Deterministic checks run first because they are free. If a draft is already
    unreadable by measurement, there is no reason to spend a judge call
    confirming it — but we still run the judge so the rejection log is complete
    and the memory store gets a full picture of what failed together.
    """
    from .deterministic import run_deterministic_checks

    results = run_deterministic_checks(lesson, settings.readability)

    try:
        judged, usage = judge_lesson(lesson=lesson, provider=provider, settings=settings)
    except ProviderError as exc:
        # The judge failing is not a pass. Fail every judged blocking check
        # loudly rather than shipping something nobody evaluated.
        judged = [
            CheckResult(
                check_id=spec.id,
                passed=False,
                reason=f"Evaluator call failed: {exc}",
                evidence="",
                kind=CheckKind.JUDGED,
                blocking=spec.blocking,
            )
            for spec in JUDGED_CHECKS
        ]
        usage = None

    results.extend(judged)

    # Emit in registry order so every report reads the same way.
    order = {cid: i for i, cid in enumerate(BY_ID)}
    results.sort(key=lambda r: order.get(r.check_id, 999))

    return Evaluation(attempt=attempt, results=results), usage
