"""Web dashboard for watching the loop work.

Two modes, and the split is deliberate:

* **Replay** — animates a run that already happened, from its `run.json`. No API
  key, no network, no quota, identical every time. This is the mode to record a
  demo with, because a live model failing mid-take is a bad reason to lose a
  recording.
* **Live** — actually executes the graph and streams events as they occur. This
  is the mode that proves the replay is not a mockup.

Both feed the same event stream and the same UI, so what you see in a replay is
exactly what the live run produced.

Run with:  make dashboard
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from lessonforge.config import PROJECT_ROOT, load_settings
from lessonforge.graph import build_graph
from lessonforge.inject import INJECTIONS
from lessonforge.llm import build_provider
from lessonforge.llm.base import ProviderError
from lessonforge.memory import MemoryStore
from lessonforge.report import write_outputs
from lessonforge.rubric.registry import RUBRIC
from lessonforge.state import new_state

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="lessonforge dashboard")


# --------------------------------------------------------------------- models


class RunRequest(BaseModel):
    topic: str = "Introduction to RAG (Retrieval-Augmented Generation)"
    provider: str = "mock"
    inject_error: str | None = None
    generator_model: str | None = None
    judge_model: str | None = None


# ----------------------------------------------------------------- run registry

# In-process registry of active runs. A dashboard for one person on one machine
# does not need a job store; if this ever served more than that, this is the
# first thing to replace.
_streams: dict[str, queue.Queue] = {}
_counter = {"n": 0}
_lock = threading.Lock()


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


# ------------------------------------------------------------------- endpoints


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/rubric")
def get_rubric() -> list[dict]:
    """The checklist the UI renders before any run starts."""
    return [
        {
            "id": c.id,
            "dimension": c.dimension.value,
            "kind": c.kind.value,
            "blocking": c.blocking,
            "title": c.title,
            "remediation": c.remediation_hint,
        }
        for c in RUBRIC
    ]


@app.get("/api/injections")
def get_injections() -> list[dict]:
    return [
        {"mode": i.mode, "description": i.description, "expects": list(i.expects_failure_of)}
        for i in INJECTIONS.values()
    ]


@app.get("/api/memory")
def get_memory() -> dict:
    settings = load_settings()
    store = MemoryStore(settings.memory_db)
    stats = store.stats()
    stats["patches"] = [
        {"check_id": p.check_id, "directive": p.directive, "times_applied": p.times_applied}
        for p in store.active_patches(limit=20)
    ]
    stats["failures"] = [
        {"check_id": f.check_id, "fails": f.fail_count, "reason": f.last_reason}
        for f in store.failure_patterns(min_failures=1)[:12]
    ]
    return stats


@app.get("/api/recorded")
def list_recorded() -> list[dict]:
    """Runs on disk that can be replayed."""
    out = load_settings().output_dir
    runs = []
    for d in sorted(out.glob("*/"), reverse=True):
        trace = d / "run.json"
        if not trace.exists():
            continue
        try:
            data = json.loads(trace.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        runs.append(
            {
                "id": d.name,
                "topic": data.get("topic", "unknown"),
                "attempts": data.get("attempts", 0),
                "shipped": bool(data.get("shipped")),
                "provider": data.get("provider"),
                "generated_at": data.get("generated_at"),
                "injected_error": data.get("injected_error"),
            }
        )
    return runs


@app.get("/api/recorded/{run_id}")
def get_recorded(run_id: str) -> dict:
    out = load_settings().output_dir
    # Reject path traversal: only a direct child of the output directory.
    directory = (out / run_id).resolve()
    if not str(directory).startswith(str(out.resolve())) or not directory.is_dir():
        raise HTTPException(404, "No such run")

    trace = directory / "run.json"
    if not trace.exists():
        raise HTTPException(404, "Run has no trace")

    data = json.loads(trace.read_text(encoding="utf-8"))

    drafts = []
    for path in sorted((directory / "drafts").glob("attempt_*.md")):
        drafts.append({"name": path.stem, "markdown": path.read_text(encoding="utf-8")})
    if not drafts:
        for name in ("lesson.md", "rejected_draft.md"):
            p = directory / name
            if p.exists():
                drafts.append({"name": p.stem, "markdown": p.read_text(encoding="utf-8")})

    lesson = directory / "lesson.md"
    log = directory / "rejection_log.md"
    data["drafts"] = drafts
    data["lesson"] = lesson.read_text(encoding="utf-8") if lesson.exists() else None
    data["rejection_log"] = log.read_text(encoding="utf-8") if log.exists() else None
    return data


# ------------------------------------------------------------------- live run


def _execute(run_key: str, req: RunRequest) -> None:
    """Run the graph on a worker thread, pushing events onto the queue."""
    q = _streams[run_key]

    def emit(kind: str, **payload: Any) -> None:
        q.put({"kind": kind, **payload})

    try:
        settings = load_settings(
            provider=req.provider,
            generator_model=req.generator_model,
            judge_model=req.judge_model,
        )
        if req.provider == "mock":
            # Keep a demo run out of the real memory store, so replaying the UI
            # does not quietly pollute the metrics the project reports on.
            settings = replace(settings, memory_db=PROJECT_ROOT / "memory" / "dashboard.db")

        provider = build_provider(settings)
        store = MemoryStore(settings.memory_db)

        emit(
            "start",
            topic=req.topic,
            provider=settings.provider,
            generator=settings.generator_model,
            judge=settings.judge_model,
            inject=req.inject_error,
            max_attempts=min(settings.loop.max_retries + 1, settings.loop.hard_cap_attempts),
        )

        from lessonforge.memory import build_patch_block

        _, patch_ids = build_patch_block(store, settings)
        run_id = store.start_run(
            topic=req.topic,
            provider=settings.provider,
            generator_model=settings.generator_model,
            judge_model=settings.judge_model,
            injected_error=req.inject_error,
            patches_applied=len(patch_ids),
        )

        state = new_state(req.topic, inject_error=req.inject_error)
        state["run_id"] = run_id

        graph = build_graph(provider=provider, settings=settings, store=store)
        limit = 6 + settings.loop.hard_cap_attempts * 2 + 4

        seen_events = 0
        seen_evals = 0
        seen_drafts = 0
        final: dict = state

        for chunk in graph.stream(
            state, stream_mode="values", config={"recursion_limit": limit}
        ):
            final = chunk

            for event in (chunk.get("events") or [])[seen_events:]:
                emit("node", event=event)
            seen_events = len(chunk.get("events") or [])

            for evaluation in (chunk.get("evaluations") or [])[seen_evals:]:
                emit(
                    "evaluation",
                    attempt=evaluation.attempt,
                    passed=evaluation.passed,
                    summary=evaluation.summary,
                    results=[r.model_dump(mode="json") for r in evaluation.results],
                )
            seen_evals = len(chunk.get("evaluations") or [])

            # Only when a *new* draft appears. LangGraph yields the full state
            # on every step, so emitting on presence rather than on change sent
            # the same draft repeatedly.
            drafts = chunk.get("drafts") or []
            if len(drafts) > seen_drafts:
                emit("draft", index=len(drafts), markdown=drafts[-1])
                seen_drafts = len(drafts)

        written = write_outputs(final, settings)
        emit(
            "done",
            shipped=bool(final.get("shipped")),
            attempts=len(final.get("evaluations") or []),
            error=final.get("error"),
            output_dir=written.get("rejection_log", Path("")).parent.name,
            usage=(final.get("usage").as_dict() if final.get("usage") else None),
        )

    except ProviderError as exc:
        emit("error", message=str(exc))
    except Exception as exc:  # noqa: BLE001 - surface anything to the UI
        emit("error", message=f"{type(exc).__name__}: {exc}")
    finally:
        q.put(None)  # sentinel: stream complete


@app.post("/api/run")
def start_run(req: RunRequest) -> dict:
    with _lock:
        _counter["n"] += 1
        run_key = f"run-{_counter['n']}"
    _streams[run_key] = queue.Queue()
    threading.Thread(target=_execute, args=(run_key, req), daemon=True).start()
    return {"stream": run_key}


@app.get("/api/stream/{run_key}")
async def stream(run_key: str) -> StreamingResponse:
    q = _streams.get(run_key)
    if q is None:
        raise HTTPException(404, "No such run")

    async def events() -> Iterator[str]:
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, q.get)
            if item is None:
                yield _sse({"kind": "end"})
                break
            yield _sse(item)
        _streams.pop(run_key, None)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------- verify


@app.post("/api/verify")
def start_verify(req: RunRequest) -> dict:
    with _lock:
        _counter["n"] += 1
        run_key = f"verify-{_counter['n']}"
    _streams[run_key] = queue.Queue()
    threading.Thread(target=_run_verify, args=(run_key, req), daemon=True).start()
    return {"stream": run_key}


def _run_verify(run_key: str, req: RunRequest) -> None:
    from lessonforge.verify import verify_evaluator

    q = _streams[run_key]

    def emit(kind: str, **payload: Any) -> None:
        q.put({"kind": kind, **payload})

    try:
        settings = load_settings(provider=req.provider, judge_model=req.judge_model)
        provider = build_provider(settings)

        emit("verify_start", judge=settings.judge_model, provider=settings.provider)

        report = verify_evaluator(
            provider=provider,
            settings=settings,
            on_progress=lambda stage, detail: emit("verify_step", stage=stage, detail=detail),
        )

        emit(
            "verify_done",
            valid=report.valid,
            baseline_passed=report.baseline_passed,
            baseline_failures=report.baseline_failures,
            any_errored=report.any_errored,
            all_caught=report.all_caught,
            outcomes=[
                {
                    "mode": o.mode,
                    "description": o.description,
                    "expected": o.expected,
                    "caught": o.caught,
                    "missed": o.missed,
                    "collateral": o.collateral,
                    "inconclusive": o.inconclusive,
                }
                for o in report.outcomes
            ],
        )
    except Exception as exc:  # noqa: BLE001
        emit("error", message=f"{type(exc).__name__}: {exc}")
    finally:
        q.put(None)


def main() -> None:
    import uvicorn

    print("\n  lessonforge dashboard → http://127.0.0.1:8000\n")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
