"""The agentic loop, as a LangGraph state machine.

    START
      │
      ▼
  ┌────────┐   once per run: blueprint + learned directives from memory
  │  plan  │
  └───┬────┘
      │
      ▼
  ┌──────────┐◄─────────────────────────┐
  │ generate │   attempt N               │
  └───┬──────┘                           │
      │                                  │
      ▼                                  │
  ┌──────────┐   deterministic + judged  │
  │ evaluate │   -> pass / fail          │
  └───┬──────┘                           │
      │                                  │
      ▼                                  │
   ╔══════╗  fail AND attempts remaining │
   ║ gate ║──────────────────────────────┘
   ╚══┬═══╝
      │ pass, or retries exhausted
      ▼
  ┌─────────┐
  │ reflect │   learn from failures -> new standing directives
  └───┬─────┘
      │
      ▼
  ┌─────────┐
  │ persist │   close the run record
  └───┬─────┘
      │
      ▼
     END

Why LangGraph rather than a `while` loop
----------------------------------------
The control flow here genuinely is a state machine with a conditional cycle, and
LangGraph makes that structure explicit rather than implicit in nesting. Three
concrete payoffs:

* the termination condition lives in one named function (`gate`) that can be
  unit-tested on its own, instead of being spread across loop conditions;
* accumulated state (every draft, every evaluation) is declared in the state
  schema with explicit reducers, which is what makes the rejection log a
  projection of real data rather than a separately maintained side-list;
* the graph is inspectable — `lessonforge graph` prints the topology, and the
  same object supports checkpointing and streaming without restructuring.

Termination is guaranteed twice over: the gate refuses to loop past
`max_retries`, and `hard_cap_attempts` is an independent ceiling that holds even
if the policy is misconfigured.
"""

from __future__ import annotations

from functools import partial
from typing import Callable

from langgraph.graph import END, START, StateGraph

from .config import Settings
from .llm.base import LLMProvider
from .memory import MemoryStore
from .nodes import (
    evaluate_node,
    generate_node,
    persist_node,
    plan_node,
    reflect_node,
)
from .state import ForgeState

RETRY = "generate"
PROCEED = "reflect"


def gate(state: ForgeState, *, settings: Settings) -> str:
    """Decide whether to regenerate or move on.

    Pure function of state — no I/O, no model call. Everything about when this
    system stops is decided here and nowhere else.
    """
    if state.get("error"):
        return PROCEED  # hard failure: stop looping, record what happened

    evaluations = state.get("evaluations") or []
    if not evaluations:
        return PROCEED

    latest = evaluations[-1]
    if latest.passed and settings.loop.stop_on_first_pass:
        return PROCEED

    attempt = state.get("attempt", 0)
    max_attempts = min(
        settings.loop.max_retries + 1, settings.loop.hard_cap_attempts
    )
    if attempt >= max_attempts:
        return PROCEED

    return RETRY


def _finalise(state: ForgeState, *, settings: Settings) -> dict:
    """Set the shipped/exhausted flags before reflection and persistence."""
    evaluations = state.get("evaluations") or []
    passed = bool(evaluations and evaluations[-1].passed)
    attempt = state.get("attempt", 0)
    max_attempts = min(settings.loop.max_retries + 1, settings.loop.hard_cap_attempts)

    return {
        "shipped": passed,
        "exhausted": not passed and attempt >= max_attempts,
        "events": [
            {
                "node": "gate",
                "status": "shipped" if passed else "rejected",
                "attempts_used": attempt,
                "max_attempts": max_attempts,
            }
        ],
    }


def build_graph(
    *, provider: LLMProvider, settings: Settings, store: MemoryStore
) -> Callable:
    """Compile the state machine with dependencies bound into each node."""
    graph = StateGraph(ForgeState)

    graph.add_node("plan", partial(plan_node, provider=provider, settings=settings, store=store))
    graph.add_node("generate", partial(generate_node, provider=provider, settings=settings))
    graph.add_node(
        "evaluate", partial(evaluate_node, provider=provider, settings=settings, store=store)
    )
    graph.add_node("finalise", partial(_finalise, settings=settings))
    graph.add_node(
        "reflect", partial(reflect_node, provider=provider, settings=settings, store=store)
    )
    graph.add_node("persist", partial(persist_node, settings=settings, store=store))

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "generate")
    graph.add_edge("generate", "evaluate")

    # The cycle. This single conditional edge is the whole self-correction loop.
    graph.add_conditional_edges(
        "evaluate",
        partial(gate, settings=settings),
        {RETRY: "generate", PROCEED: "finalise"},
    )

    graph.add_edge("finalise", "reflect")
    graph.add_edge("reflect", "persist")
    graph.add_edge("persist", END)

    return graph.compile()


def describe_graph() -> str:
    """Human-readable topology, for `lessonforge graph` and the README."""
    return """
START → plan → generate → evaluate → ⟨gate⟩ ─┬─ fail & retries left → generate ↺
                                              └─ pass / exhausted   → finalise
finalise → reflect → persist → END

nodes
  plan      Planner LLM  · topic → blueprint; loads learned directives from memory
  generate  Generator LLM · blueprint + directives + prior failures → lesson markdown
  evaluate  Deterministic checks (local) + Judge LLM (isolated) → pass/fail per check
  gate      Pure function · retry, or stop. The only place termination is decided.
  finalise  Sets shipped / exhausted flags
  reflect   Reflector LLM · repeated failures → new standing directives (self-evolving)
  persist   Closes the run record in SQLite
""".strip()
