"""Output artefacts.

Three files per run:

* `lesson.md`        — the shippable lesson (only written when it passed)
* `rejection_log.md` — what failed, why, and what changed on retry
* `run.json`         — the full machine-readable trace

The rejection log is the deliverable that proves the loop is real. Anyone can
show a good final lesson; the log is what shows the system rejected its own work
and says exactly why.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .rubric.deterministic import analyse
from .rubric.registry import BY_ID, RUBRIC
from .rubric.schema import Evaluation
from .state import ForgeState


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _slug(text: str, limit: int = 40) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:limit] or "lesson"


def run_dir(settings: Settings, topic: str) -> Path:
    path = settings.output_dir / f"{_ts()}-{_slug(topic)}"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ------------------------------------------------------------- rejection log


def _status_icon(passed: bool, blocking: bool) -> str:
    if passed:
        return "PASS"
    return "**FAIL**" if blocking else "warn"


def _evaluation_table(evaluation: Evaluation) -> str:
    rows = [
        "| Check | Dimension | Type | Result |",
        "| --- | --- | --- | --- |",
    ]
    for result in evaluation.results:
        spec = BY_ID.get(result.check_id)
        dim = spec.dimension.value if spec else "-"
        rows.append(
            f"| `{result.check_id}` | {dim} | {result.kind.value} | "
            f"{_status_icon(result.passed, result.blocking)} |"
        )
    return "\n".join(rows)


def _diff_summary(prev: Evaluation, curr: Evaluation) -> str:
    prev_failed = {r.check_id for r in prev.blocking_failures}
    curr_failed = {r.check_id for r in curr.blocking_failures}

    fixed = sorted(prev_failed - curr_failed)
    still = sorted(prev_failed & curr_failed)
    new = sorted(curr_failed - prev_failed)

    lines = []
    if fixed:
        lines.append(f"- **Fixed:** {', '.join(f'`{c}`' for c in fixed)}")
    if still:
        lines.append(f"- **Still failing:** {', '.join(f'`{c}`' for c in still)}")
    if new:
        lines.append(
            f"- **Newly broken (regression):** {', '.join(f'`{c}`' for c in new)}"
        )
    if not lines:
        lines.append("- No change in blocking failures.")
    return "\n".join(lines)


def build_rejection_log(state: ForgeState, settings: Settings) -> str:
    topic = state.get("topic", "unknown")
    evaluations: list[Evaluation] = state.get("evaluations") or []
    drafts: list[str] = state.get("drafts") or []
    shipped = bool(state.get("shipped"))
    events = state.get("events") or []

    out: list[str] = [
        f"# Rejection Log — {topic}",
        "",
        f"- **Generated:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- **Provider / models:** {settings.provider} · "
        f"gen `{settings.generator_model}` · judge `{settings.judge_model}`",
        f"- **Attempts used:** {len(evaluations)} "
        f"(max {min(settings.loop.max_retries + 1, settings.loop.hard_cap_attempts)})",
        f"- **Final outcome:** {'SHIPPED' if shipped else 'REJECTED — not shippable'}",
    ]

    injected = next((e for e in events if e.get("node") == "inject"), None)
    if injected:
        out += [
            f"- **Deliberate error injected:** `{injected.get('mode')}` "
            f"(expected to fail: "
            f"{', '.join('`' + c + '`' for c in injected.get('expected_failures', []))})",
        ]

    patches = next(
        (e for e in events if e.get("node") == "plan" and "patches_applied" in e), None
    )
    if patches:
        out.append(
            f"- **Learned directives applied from memory:** {patches['patches_applied']}"
        )

    out += ["", "---", ""]

    if not evaluations:
        out += ["No evaluations were recorded. The run failed before the loop began.", ""]
        if state.get("error"):
            out += [f"**Error:** {state['error']}", ""]
        return "\n".join(out)

    for idx, evaluation in enumerate(evaluations):
        n = evaluation.attempt
        verdict = "PASSED — shippable" if evaluation.passed else "REJECTED"
        draft = drafts[idx] if idx < len(drafts) else ""
        stats = analyse(draft, settings.readability.long_sentence_words) if draft else None

        out += [f"## Attempt {n} — {verdict}", ""]
        if stats:
            out.append(
                f"`{stats.word_count} words · {stats.sentence_count} sentences · "
                f"avg {stats.avg_sentence_words} words/sentence · "
                f"Flesch-Kincaid grade {stats.flesch_kincaid_grade}`"
            )
            out.append("")

        out += [evaluation.summary, "", _evaluation_table(evaluation), ""]

        failures = evaluation.blocking_failures
        if failures:
            out += [f"### Why it was rejected ({len(failures)} blocking failures)", ""]
            for result in failures:
                spec = BY_ID.get(result.check_id)
                out.append(f"**`{result.check_id}` — {spec.title if spec else ''}**")
                out.append("")
                out.append(f"- *Reason:* {result.reason}")
                if result.evidence:
                    ev = result.evidence.strip().replace("\n", " ")
                    out.append(f"- *Evidence from the draft:* “{ev[:400]}”")
                if spec:
                    out.append(f"- *Required fix:* {spec.remediation_hint}")
                out.append("")
        else:
            out += ["All blocking checks passed.", ""]

        advisory = evaluation.advisory_failures
        if advisory:
            out += ["### Advisory (did not block shipping)", ""]
            for result in advisory:
                out.append(f"- `{result.check_id}`: {result.reason}")
            out.append("")

        if idx + 1 < len(evaluations):
            out += [
                f"### What changed going into attempt {evaluations[idx + 1].attempt}",
                "",
                "The failures above were fed back to the generator as a structured "
                "revision brief — the failing check, the reason, the quoted "
                "offending text, and the required fix — with an instruction to "
                "preserve everything that was not flagged.",
                "",
                _diff_summary(evaluation, evaluations[idx + 1]),
                "",
                "---",
                "",
            ]

    out += ["", "---", "", "## Outcome", ""]
    if shipped:
        out.append(
            f"The lesson passed every blocking check on attempt "
            f"{evaluations[-1].attempt} and was written to `lesson.md`."
        )
    else:
        out.append(
            "The loop exhausted its retry budget without clearing every blocking "
            "check. **No lesson was shipped.** The best draft is saved as "
            "`rejected_draft.md` for human review. Failing closed is deliberate: "
            "shipping content that the system itself judged inadequate would "
            "defeat the point of evaluating it."
        )
    out.append("")

    reflect = next((e for e in events if e.get("node") == "reflect"), None)
    if reflect and reflect.get("new_patches"):
        out += [
            "## What the system learned from this run",
            "",
            "These directives were added to the generator's standing instructions "
            "and will apply to every future run, before the first attempt:",
            "",
        ]
        for patch in reflect["new_patches"]:
            out.append(f"- (`{patch['check_id']}`) {patch['directive']}")
        out.append("")

    if reflect and reflect.get("non_discriminating"):
        out += [
            "## Rubric health warning",
            "",
            "These blocking checks have never failed across the recorded history. "
            "They are either genuinely solved or silently broken. Flagged for "
            "human review — the system does not modify its own rubric.",
            "",
        ]
        for check_id in reflect["non_discriminating"]:
            out.append(f"- `{check_id}`")
        out.append("")

    return "\n".join(out)


# -------------------------------------------------------------- json trace


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def build_trace(state: ForgeState, settings: Settings) -> dict:
    evaluations: list[Evaluation] = state.get("evaluations") or []
    usage = state.get("usage")

    return {
        "topic": state.get("topic"),
        "run_id": state.get("run_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provider": settings.provider,
        "models": {
            "planner": settings.planner_model,
            "generator": settings.generator_model,
            "judge": settings.judge_model,
            "reflector": settings.reflector_model,
        },
        "policy": {
            "max_retries": settings.loop.max_retries,
            "hard_cap_attempts": settings.loop.hard_cap_attempts,
            "evolution_enabled": settings.evolution.enabled,
            "patch_threshold": settings.evolution.patch_threshold,
        },
        "injected_error": state.get("inject_error"),
        "attempts": len(evaluations),
        "shipped": bool(state.get("shipped")),
        "exhausted": bool(state.get("exhausted")),
        "error": state.get("error"),
        "usage": _jsonable(usage) if usage else None,
        "plan": _jsonable(state.get("plan")),
        "evaluations": [
            {
                "attempt": e.attempt,
                "passed": e.passed,
                "summary": e.summary,
                "results": [_jsonable(r) for r in e.results],
            }
            for e in evaluations
        ],
        "events": state.get("events") or [],
    }


# ------------------------------------------------------------------ writing


def write_outputs(state: ForgeState, settings: Settings) -> dict[str, Path]:
    """Write all artefacts for a run. Returns a name -> path map."""
    directory = run_dir(settings, state.get("topic", "lesson"))
    written: dict[str, Path] = {}

    lesson = state.get("lesson", "")
    shipped = bool(state.get("shipped"))

    if lesson:
        name = "lesson.md" if shipped else "rejected_draft.md"
        path = directory / name
        path.write_text(lesson, encoding="utf-8")
        written["lesson" if shipped else "rejected_draft"] = path

    log_path = directory / "rejection_log.md"
    log_path.write_text(build_rejection_log(state, settings), encoding="utf-8")
    written["rejection_log"] = log_path

    trace_path = directory / "run.json"
    trace_path.write_text(
        json.dumps(build_trace(state, settings), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    written["trace"] = trace_path

    # Every intermediate draft, so the progression is inspectable rather than
    # asserted.
    drafts = state.get("drafts") or []
    if len(drafts) > 1:
        drafts_dir = directory / "drafts"
        drafts_dir.mkdir(exist_ok=True)
        for i, draft in enumerate(drafts, start=1):
            (drafts_dir / f"attempt_{i}.md").write_text(draft, encoding="utf-8")
        written["drafts"] = drafts_dir

    return written


def rubric_markdown() -> str:
    """Render the rubric as a table, for RUBRIC.md and `lessonforge rubric`."""
    lines = [
        "| # | Check | Dimension | Engine | Blocking | What it tests |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for i, spec in enumerate(RUBRIC, start=1):
        lines.append(
            f"| {i} | `{spec.id}` | {spec.dimension.value} | {spec.kind.value} | "
            f"{'yes' if spec.blocking else 'advisory'} | {spec.title} |"
        )
    return "\n".join(lines)
