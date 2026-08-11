"""Planner node: topic -> lesson blueprint.

Runs once per run, before the loop. Retries reuse the plan rather than
re-deriving it, so a language failure costs one rewrite instead of a whole
re-think, and the concept ordering stays stable across attempts.
"""

from __future__ import annotations

from ..config import Settings
from ..llm.base import LLMProvider, ProviderError
from ..memory import MemoryStore, build_patch_block
from ..models import LessonPlan
from ..state import ForgeState


def plan_node(
    state: ForgeState, *, provider: LLMProvider, settings: Settings, store: MemoryStore
) -> dict:
    topic = state["topic"]

    # Load learned directives from previous runs *before* the first generation.
    # This is the point where memory becomes causal rather than decorative.
    patch_block, patch_ids = build_patch_block(store, settings)

    prompt = (
        settings.prompt("planner")
        .replace("{{GROUND_TRUTH}}", settings.ground_truth())
        .replace("{{TOPIC}}", topic)
    )

    try:
        completion = provider.complete_structured(
            model=settings.planner_model,
            prompt=prompt,
            schema=LessonPlan,
            temperature=0.4,
            max_output_tokens=4000,
        )
    except ProviderError as exc:
        return {
            "error": f"Planner failed: {exc}",
            "events": [{"node": "plan", "status": "error", "detail": str(exc)}],
        }

    plan: LessonPlan = completion.parsed

    return {
        "plan": plan,
        "patch_block": patch_block,
        "applied_patch_ids": patch_ids,
        "usage": completion.usage,
        "events": [
            {
                "node": "plan",
                "status": "ok",
                "objectives": len(plan.learning_objectives),
                "concepts": len(plan.concept_order),
                "analogy": plan.analogy,
                "patches_applied": len(patch_ids),
            }
        ],
    }
