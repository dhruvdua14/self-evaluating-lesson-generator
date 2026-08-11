"""LangGraph state.

One mutable object flows through the graph. Keeping every attempt and every
evaluation in the state (rather than overwriting) is what makes the rejection
log possible — the report is a projection of this object, not something
assembled separately and hoped to be accurate.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from .llm.base import Usage
from .models import LessonPlan
from .rubric.schema import Evaluation


def _keep_last(_old: Any, new: Any) -> Any:
    return new


def _append(old: list, new: list) -> list:
    return (old or []) + (new or [])


def _sum_usage(old: Usage | None, new: Usage | None) -> Usage:
    base = old or Usage()
    return base.add(new) if new else base


class ForgeState(TypedDict, total=False):
    """State passed between graph nodes."""

    # --- inputs
    topic: str
    run_id: int
    inject_error: str | None

    # --- planning
    plan: Annotated[LessonPlan | None, _keep_last]
    patch_block: Annotated[str, _keep_last]
    applied_patch_ids: Annotated[list[int], _keep_last]

    # --- loop
    attempt: Annotated[int, _keep_last]
    lesson: Annotated[str, _keep_last]
    drafts: Annotated[list[str], _append]
    evaluations: Annotated[list[Evaluation], _append]
    feedback: Annotated[str, _keep_last]

    # --- outcome
    shipped: Annotated[bool, _keep_last]
    exhausted: Annotated[bool, _keep_last]
    usage: Annotated[Usage, _sum_usage]
    events: Annotated[list[dict], _append]
    error: Annotated[str | None, _keep_last]


def new_state(topic: str, *, inject_error: str | None = None) -> ForgeState:
    return ForgeState(
        topic=topic,
        inject_error=inject_error,
        attempt=0,
        lesson="",
        drafts=[],
        evaluations=[],
        feedback="",
        patch_block="",
        applied_patch_ids=[],
        shipped=False,
        exhausted=False,
        usage=Usage(),
        events=[],
        error=None,
    )
