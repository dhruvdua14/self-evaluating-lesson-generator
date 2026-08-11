"""The self-evolving layer.

The loop in `graph.py` fixes one lesson. This module fixes the *generator*, so
the next lesson needs fewer fixes.

How it works
------------
1. After every run, failure counts are aggregated across the whole memory store.
2. Any check that has now failed `patch_threshold` times and does not already
   have an active directive becomes a candidate.
3. The Reflector (an LLM call with a schema) reads the candidate's real failure
   reasons and writes one imperative sentence that would have prevented them.
4. That sentence is stored and injected into the generator's system prompt on
   **every subsequent run, before the first attempt**.

The measurable claim is narrow and testable: first-attempt pass rate should rise
as patches accumulate. `lessonforge memory` prints exactly that number, so the
claim can be falsified.

Two guard rails, because a system that edits its own prompt can drift:

* Patches are capped (`max_active_patches`) and deduplicated on exact text, so
  the system prompt cannot grow without bound.
* The rubric is **never** modified automatically. Checks that stop discriminating
  are reported to a human. A loop allowed to relax its own passing criteria will
  eventually pass everything, which is the failure mode this whole design exists
  to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings
from ..llm.base import LLMProvider, ProviderError
from ..models import ReflectionOutput
from ..rubric.registry import BY_ID
from .store import MemoryStore


@dataclass
class EvolutionReport:
    candidates: list[str]
    new_patches: list[tuple[str, str]]  # (check_id, directive)
    skipped: list[str]
    non_discriminating: list[str]
    error: str | None = None

    @property
    def changed(self) -> bool:
        return bool(self.new_patches)


def build_patch_block(store: MemoryStore, settings: Settings) -> tuple[str, list[int]]:
    """Render active directives for injection into the generator system prompt.

    Returns the text block and the patch ids applied, so usage can be counted.

    Honours `evolution.enabled`. That flag previously governed only whether *new*
    directives were learned, while previously learned ones were still injected —
    which made `--no-evolve` useless for the one experiment it exists to support:
    holding the code fixed and measuring what the directives are actually worth.
    A control that silently applies the treatment is not a control.
    """
    if not settings.evolution.enabled:
        return "", []

    patches = store.active_patches(limit=settings.evolution.max_active_patches)
    if not patches:
        return "", []

    lines = [
        "## Learned directives (from previous failed runs)",
        "",
        "These rules were derived from real rubric failures on earlier lessons.",
        "Follow every one of them.",
        "",
    ]
    lines += [f"{i}. {p.directive}" for i, p in enumerate(patches, start=1)]
    return "\n".join(lines), [p.id for p in patches]


def reflect_and_evolve(
    *,
    store: MemoryStore,
    provider: LLMProvider,
    settings: Settings,
    run_id: int | None,
) -> EvolutionReport:
    """Synthesise new generator directives from repeated rubric failures."""
    policy = settings.evolution
    if not policy.enabled:
        return EvolutionReport([], [], [], [])

    patterns = store.failure_patterns(min_failures=policy.patch_threshold)
    non_discriminating = store.non_discriminating_checks(
        after_runs=policy.non_discriminating_after_runs
    )

    candidates = []
    skipped = []
    for p in patterns:
        if p.check_id not in BY_ID:
            continue
        if store.has_patch_for(p.check_id):
            skipped.append(p.check_id)
            continue
        candidates.append(p)

    # Blocking checks first. `failure_patterns` orders by raw failure count, and
    # ties break alphabetically — without this, an advisory check like
    # `length_in_range` can occupy a patch slot ahead of a blocking one purely
    # because of its name. Blocking failures are the ones that stop a lesson
    # shipping, so they get the scarce slots.
    candidates.sort(key=lambda p: (not BY_ID[p.check_id].blocking, -p.fail_count, p.check_id))

    if not candidates:
        return EvolutionReport(
            candidates=[],
            new_patches=[],
            skipped=skipped,
            non_discriminating=non_discriminating,
        )

    active_count = len(store.active_patches(limit=policy.max_active_patches + 1))
    room = max(0, policy.max_active_patches - active_count)
    if room == 0:
        return EvolutionReport(
            candidates=[c.check_id for c in candidates],
            new_patches=[],
            skipped=skipped + [c.check_id for c in candidates],
            non_discriminating=non_discriminating,
        )

    candidates = candidates[:room]

    evidence_lines = []
    for c in candidates:
        spec = BY_ID[c.check_id]
        evidence_lines.append(
            f"- check_id: {c.check_id}\n"
            f"  what it tests: {spec.title}\n"
            f"  times failed: {c.fail_count}\n"
            f"  most recent failure reason: {c.last_reason or '(none recorded)'}\n"
            f"  existing remediation hint: {spec.remediation_hint}"
        )

    prompt = settings.prompt("reflector").replace(
        "{{FAILURES}}", "\n".join(evidence_lines)
    )

    try:
        completion = provider.complete_structured(
            model=settings.reflector_model,
            prompt=prompt,
            schema=ReflectionOutput,
            temperature=0.2,
            max_output_tokens=2000,
        )
    except ProviderError as exc:
        # Evolution is an optimisation, never a hard dependency. A reflector
        # failure must not fail a run that already produced a shippable lesson.
        return EvolutionReport(
            candidates=[c.check_id for c in candidates],
            new_patches=[],
            skipped=skipped,
            non_discriminating=non_discriminating,
            error=str(exc),
        )

    reflection: ReflectionOutput = completion.parsed
    new_patches: list[tuple[str, str]] = []
    allowed = {c.check_id for c in candidates}

    for proposal in reflection.patches:
        if proposal.check_id not in allowed:
            continue  # Reflector may only patch checks we asked about.
        directive = proposal.directive.strip()
        if not directive or len(directive) > 400:
            continue
        if store.add_patch(
            check_id=proposal.check_id,
            directive=directive,
            rationale=proposal.rationale,
            source_run_id=run_id,
        ):
            new_patches.append((proposal.check_id, directive))

    return EvolutionReport(
        candidates=[c.check_id for c in candidates],
        new_patches=new_patches,
        skipped=skipped,
        non_discriminating=non_discriminating,
    )
