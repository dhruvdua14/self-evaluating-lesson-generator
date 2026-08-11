"""Persistent memory: SQLite.

What memory is for here
-----------------------
Not conversation history. This store answers one question across the lifetime of
the system: **which rubric checks does the generator keep failing, and what
should we tell it up front so it stops?**

Three things persist:

* **Evidence** — every attempt and every individual check verdict, so failure
  rates are measured rather than guessed.
* **Learned directives** (`prompt_patches`) — imperative sentences synthesised
  from repeated failures and injected into the generator's system prompt on
  every future run, before the first attempt.
* **Outcomes** — enough per-run data to show that first-attempt pass rate moves
  as patches accumulate. If that number does not improve, the self-evolving
  layer is decoration, and the store is what proves it either way.

SQLite rather than a vector store on purpose: this data is small, relational,
and queried by exact key. Similarity search would add a dependency and answer a
question nobody is asking.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from ..rubric.schema import Evaluation

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    topic             TEXT    NOT NULL,
    started_at        TEXT    NOT NULL,
    finished_at       TEXT,
    provider          TEXT    NOT NULL,
    generator_model   TEXT    NOT NULL,
    judge_model       TEXT    NOT NULL,
    attempts          INTEGER DEFAULT 0,
    shipped           INTEGER DEFAULT 0,
    first_attempt_ok  INTEGER,
    injected_error    TEXT,
    patches_applied   INTEGER DEFAULT 0,
    input_tokens      INTEGER DEFAULT 0,
    output_tokens     INTEGER DEFAULT 0,
    api_calls         INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS attempt_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    attempt_no  INTEGER NOT NULL,
    passed      INTEGER NOT NULL,
    word_count  INTEGER DEFAULT 0,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS check_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    attempt_no  INTEGER NOT NULL,
    check_id    TEXT    NOT NULL,
    passed      INTEGER NOT NULL,
    blocking    INTEGER NOT NULL,
    kind        TEXT    NOT NULL,
    reason      TEXT    DEFAULT '',
    evidence    TEXT    DEFAULT '',
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS prompt_patches (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id      TEXT    NOT NULL,
    directive     TEXT    NOT NULL UNIQUE,
    rationale     TEXT    DEFAULT '',
    created_at    TEXT    NOT NULL,
    source_run_id INTEGER,
    active        INTEGER DEFAULT 1,
    times_applied INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS lessons (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    topic      TEXT    NOT NULL,
    markdown   TEXT    NOT NULL,
    shipped    INTEGER NOT NULL,
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_check_results_check ON check_results(check_id, passed);
CREATE INDEX IF NOT EXISTS idx_check_results_run   ON check_results(run_id);
CREATE INDEX IF NOT EXISTS idx_attempt_run         ON attempt_results(run_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class FailurePattern:
    check_id: str
    fail_count: int
    runs_seen: int
    last_reason: str


@dataclass(frozen=True)
class Patch:
    id: int
    check_id: str
    directive: str
    rationale: str
    times_applied: int


class MemoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------ runs

    def start_run(
        self,
        *,
        topic: str,
        provider: str,
        generator_model: str,
        judge_model: str,
        injected_error: str | None,
        patches_applied: int,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO runs
                   (topic, started_at, provider, generator_model, judge_model,
                    injected_error, patches_applied)
                   VALUES (?,?,?,?,?,?,?)""",
                (topic, _now(), provider, generator_model, judge_model,
                 injected_error, patches_applied),
            )
            return int(cur.lastrowid)

    def finish_run(
        self,
        run_id: int,
        *,
        attempts: int,
        shipped: bool,
        first_attempt_ok: bool,
        input_tokens: int,
        output_tokens: int,
        api_calls: int,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """UPDATE runs SET finished_at=?, attempts=?, shipped=?,
                          first_attempt_ok=?, input_tokens=?, output_tokens=?,
                          api_calls=?
                   WHERE id=?""",
                (_now(), attempts, int(shipped), int(first_attempt_ok),
                 input_tokens, output_tokens, api_calls, run_id),
            )

    # ----------------------------------------------------------- evaluations

    def record_evaluation(self, run_id: int, evaluation: Evaluation, word_count: int) -> None:
        rows = [
            (run_id, evaluation.attempt, r.check_id, int(r.passed), int(r.blocking),
             r.kind.value, r.reason, r.evidence[:1000], _now())
            for r in evaluation.results
        ]
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO attempt_results (run_id, attempt_no, passed, word_count, created_at)
                   VALUES (?,?,?,?,?)""",
                (run_id, evaluation.attempt, int(evaluation.passed), word_count, _now()),
            )
            conn.executemany(
                """INSERT INTO check_results
                   (run_id, attempt_no, check_id, passed, blocking, kind, reason, evidence, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                rows,
            )

    def record_lesson(self, run_id: int, topic: str, markdown: str, shipped: bool) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO lessons (run_id, topic, markdown, shipped, created_at)
                   VALUES (?,?,?,?,?)""",
                (run_id, topic, markdown, int(shipped), _now()),
            )

    # -------------------------------------------------------------- patterns

    def failure_patterns(self, *, min_failures: int = 1) -> list[FailurePattern]:
        """Checks ranked by how often they have failed, all runs, all attempts."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT check_id,
                          SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) AS fails,
                          COUNT(DISTINCT run_id)                      AS runs_seen
                   FROM check_results
                   GROUP BY check_id
                   HAVING fails >= ?
                   ORDER BY fails DESC, check_id ASC""",
                (min_failures,),
            ).fetchall()

            patterns = []
            for row in rows:
                reason = conn.execute(
                    """SELECT reason FROM check_results
                       WHERE check_id = ? AND passed = 0 AND reason != ''
                       ORDER BY id DESC LIMIT 1""",
                    (row["check_id"],),
                ).fetchone()
                patterns.append(
                    FailurePattern(
                        check_id=row["check_id"],
                        fail_count=int(row["fails"]),
                        runs_seen=int(row["runs_seen"]),
                        last_reason=reason["reason"] if reason else "",
                    )
                )
            return patterns

    def non_discriminating_checks(self, *, after_runs: int) -> list[str]:
        """Blocking checks that have never once failed.

        Surfaced for human review, never auto-removed. A check that never fires
        is either genuinely solved or quietly broken, and only a person can tell
        which.
        """
        with self._conn() as conn:
            total_runs = conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
            if total_runs < after_runs:
                return []
            rows = conn.execute(
                """SELECT check_id
                   FROM check_results
                   WHERE blocking = 1
                   GROUP BY check_id
                   HAVING SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) = 0
                   ORDER BY check_id"""
            ).fetchall()
            return [r["check_id"] for r in rows]

    # --------------------------------------------------------------- patches

    def active_patches(self, limit: int = 8) -> list[Patch]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, check_id, directive, rationale, times_applied
                   FROM prompt_patches WHERE active = 1
                   ORDER BY times_applied DESC, id ASC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            Patch(
                id=int(r["id"]),
                check_id=r["check_id"],
                directive=r["directive"],
                rationale=r["rationale"],
                times_applied=int(r["times_applied"]),
            )
            for r in rows
        ]

    def has_patch_for(self, check_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM prompt_patches WHERE check_id = ? AND active = 1 LIMIT 1",
                (check_id,),
            ).fetchone()
        return row is not None

    def add_patch(
        self, *, check_id: str, directive: str, rationale: str, source_run_id: int | None
    ) -> bool:
        """Insert a directive. Returns False if an identical one already exists."""
        with self._conn() as conn:
            try:
                conn.execute(
                    """INSERT INTO prompt_patches
                       (check_id, directive, rationale, created_at, source_run_id)
                       VALUES (?,?,?,?,?)""",
                    (check_id, directive.strip(), rationale.strip(), _now(), source_run_id),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def mark_patches_applied(self, patch_ids: list[int]) -> None:
        if not patch_ids:
            return
        with self._conn() as conn:
            conn.executemany(
                "UPDATE prompt_patches SET times_applied = times_applied + 1 WHERE id = ?",
                [(pid,) for pid in patch_ids],
            )

    def deactivate_patch(self, patch_id: int) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE prompt_patches SET active = 0 WHERE id = ?", (patch_id,))

    # ----------------------------------------------------------------- stats

    def stats(self) -> dict:
        """Aggregates used by `lessonforge memory` and the evolution report."""
        with self._conn() as conn:
            runs = conn.execute(
                """SELECT COUNT(*) AS total,
                          SUM(shipped) AS shipped,
                          SUM(COALESCE(first_attempt_ok,0)) AS first_ok,
                          SUM(attempts) AS total_attempts,
                          SUM(input_tokens) AS in_tok,
                          SUM(output_tokens) AS out_tok,
                          SUM(api_calls) AS calls
                   FROM runs WHERE finished_at IS NOT NULL"""
            ).fetchone()
            patches = conn.execute(
                "SELECT COUNT(*) AS n FROM prompt_patches WHERE active = 1"
            ).fetchone()["n"]

            total = int(runs["total"] or 0)
            history = conn.execute(
                """SELECT id, topic, attempts, shipped, first_attempt_ok, patches_applied,
                          started_at
                   FROM runs WHERE finished_at IS NOT NULL
                   ORDER BY id ASC"""
            ).fetchall()

        return {
            "total_runs": total,
            "shipped": int(runs["shipped"] or 0),
            "first_attempt_passes": int(runs["first_ok"] or 0),
            "first_attempt_pass_rate": (
                round(int(runs["first_ok"] or 0) / total, 3) if total else None
            ),
            "avg_attempts": (
                round(int(runs["total_attempts"] or 0) / total, 2) if total else None
            ),
            "active_patches": int(patches),
            "input_tokens": int(runs["in_tok"] or 0),
            "output_tokens": int(runs["out_tok"] or 0),
            "api_calls": int(runs["calls"] or 0),
            "history": [dict(r) for r in history],
        }

    def export(self) -> str:
        return json.dumps(self.stats(), indent=2)
