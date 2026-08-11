"""Persist node: close out the run in memory.

Deliberately separate from `reflect`. Persistence must happen even when
reflection is disabled or fails, or a run that produced a perfectly good lesson
would vanish from the record because an optimisation step errored.
"""

from __future__ import annotations

from ..config import Settings
from ..memory import MemoryStore
from ..state import ForgeState


def persist_node(state: ForgeState, *, settings: Settings, store: MemoryStore) -> dict:
    run_id = state.get("run_id")
    evaluations = state.get("evaluations") or []
    shipped = bool(state.get("shipped"))
    usage = state.get("usage")

    if run_id is None:
        return {"events": [{"node": "persist", "status": "skipped"}]}

    first_ok = bool(evaluations and evaluations[0].passed)

    store.finish_run(
        run_id,
        attempts=len(evaluations),
        shipped=shipped,
        first_attempt_ok=first_ok,
        input_tokens=getattr(usage, "input_tokens", 0),
        output_tokens=getattr(usage, "output_tokens", 0),
        api_calls=getattr(usage, "calls", 0),
    )

    lesson = state.get("lesson", "")
    if lesson:
        store.record_lesson(run_id, state["topic"], lesson, shipped)

    # Only count a directive as "used" once its run has actually completed, so
    # times_applied reflects real influence rather than intent.
    store.mark_patches_applied(state.get("applied_patch_ids") or [])

    return {
        "events": [
            {
                "node": "persist",
                "status": "ok",
                "run_id": run_id,
                "attempts": len(evaluations),
                "shipped": shipped,
                "first_attempt_ok": first_ok,
            }
        ]
    }
