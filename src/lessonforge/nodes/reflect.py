"""Reflector node: run history -> new standing directives for the generator.

Runs once, after the loop terminates, whether or not the lesson shipped. A run
that failed three times is the most informative input this node ever gets, so
skipping reflection on failure would discard the best evidence available.
"""

from __future__ import annotations

from ..config import Settings
from ..llm.base import LLMProvider
from ..memory import MemoryStore, reflect_and_evolve
from ..state import ForgeState


def reflect_node(
    state: ForgeState, *, provider: LLMProvider, settings: Settings, store: MemoryStore
) -> dict:
    if not settings.evolution.enabled:
        return {"events": [{"node": "reflect", "status": "disabled"}]}

    report = reflect_and_evolve(
        store=store,
        provider=provider,
        settings=settings,
        run_id=state.get("run_id"),
    )

    return {
        "events": [
            {
                "node": "reflect",
                "status": "error" if report.error else ("evolved" if report.changed else "stable"),
                "candidates": report.candidates,
                "new_patches": [
                    {"check_id": cid, "directive": d} for cid, d in report.new_patches
                ],
                "skipped": report.skipped,
                "non_discriminating": report.non_discriminating,
                "detail": report.error,
            }
        ]
    }
