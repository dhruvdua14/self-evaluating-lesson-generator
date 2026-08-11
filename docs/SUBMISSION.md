# Submission map

Where each requirement from the brief is satisfied, and how to check it in one
command.

## Deliverables

| Deliverable | Where |
|---|---|
| GitHub repo + README | [github.com/dhruvdua14/self-evaluating-lesson-generator](https://github.com/dhruvdua14/self-evaluating-lesson-generator) |
| Final lesson content | `output/<latest-run>/lesson.md` — paste into the Google Doc |
| Rejection log | `output/<latest-run>/rejection_log.md` |

## Pipeline requirements

| Requirement | Implementation | Verify with |
|---|---|---|
| **INPUT** — a topic, learner starts from zero | `lessonforge run --topic "..."`; audience encoded in every prompt and in `no_idioms_or_cultural_refs` | `lessonforge run --help` |
| **GENERATE** — standalone beginner lesson covering what / why / how | `nodes/plan.py` → `nodes/generate.py`; `covers_what_why_how` and `standalone_completeness` enforce it | `make run` |
| **EVALUATE** — hard pass/fail rubric, no partial credit | 18 checks in `rubric/registry.py`; verdict is a plain `AND` over 15 blocking checks; no score field exists in the data model | `make rubric` |
| **REGENERATE** — feed reasons back, max 1–2 retries, always terminates | Conditional edge in `graph.py`; `max_retries=2` plus an independent `hard_cap_attempts` ceiling | `make graph` |
| **OUTPUT** — passing lesson + rejection log | `report.py` writes `lesson.md`, `rejection_log.md`, `run.json`, and every intermediate draft | `ls output/<run>/` |

## Rubric dimension coverage

| Dimension from the brief | Checks |
|---|---|
| Accurate & grounded | `accuracy_grounded`, `no_unsupported_claims`, `no_weight_update_myth` |
| Beginner-friendly language | `readability_grade`, `sentence_length`, `no_runaway_sentence`, `no_idioms_or_cultural_refs`, `length_in_range`* |
| Teaches by example | `has_concrete_analogy`, `has_worked_example`, `example_density` |
| Clear, no unexplained jargon | `jargon_defined_on_first_use`, `jargon_density`* |
| Covers the key points | `covers_what_why_how`, `covers_three_steps` |
| Coherent teaching flow | `no_forward_references`, `standalone_completeness`, `has_recap`* |

<sub>* advisory — reported but does not block shipping.</sub>

## Cross-pipeline requirements

| Requirement | Implementation | Verify with |
|---|---|---|
| **SELF-EVOLVING** — learn from repeated failures to sharpen prompts | `memory/evolve.py`: a check failing twice across runs becomes a standing generator directive injected before attempt 1 of every future run. **Mechanism verified; quality benefit unproven** — see ARCHITECTURE.md §12a for the control run that broke the attribution | `make memory` after 2+ runs |
| **MEMORY** — persists across runs, learns from feedback and logs | `memory/store.py` (SQLite): runs, per-check verdicts, directives, lessons | `lessonforge memory --json` |
| **STACK** — LangGraph / Python + API | Python 3.11+, LangGraph state machine, Google Gemini via `google-genai`, pluggable provider protocol | `make graph` |

## Beyond the brief

| | Why it is here |
|---|---|
| `lessonforge verify` | Answers the obvious challenge to any self-evaluating system: plants seven known errors in a passing lesson and checks the checks predicted **in advance** actually fire. |
| Hybrid evaluator | Half the rubric is deterministic Python. LLMs cannot reliably count, so measurable properties are measured. |
| Judge isolation | The evaluator never sees the generation prompt, the plan, or the attempt number, so it cannot grade its own homework kindly. |
| Anti-fabrication | Judged failures must quote the lesson verbatim; unverifiable quotes are discarded. An omitted verdict counts as a failure, never a pass. |
| Fails closed | Retry budget exhausted with checks failing → nothing ships, non-zero exit. |
| Offline provider | The whole loop runs with no API key, so tests and CI need no secrets. |
| 77 tests + CI | Including a standing regression test on the rubric itself. |

## Four things this got wrong, and fixed

All four were found by the system's own tooling rather than by inspection, which
is the argument for building the tooling. Two of them are the kind of bug that
makes a quality system *report success while doing nothing*, which is worse than
having no quality system at all.

**1. Document averages hide localised damage.** `verify` predicted the `jargon`
injection would fail `readability_grade`. It did not — appending one 60-word
unreadable paragraph to a long clean lesson moved the Flesch-Kincaid grade from
4.67 to 5.62, correctly inside the limit. The check was right; the prediction was
wrong. Averages are *supposed* to survive one bad paragraph, but that is the
wrong property for a reader who only has to hit one impenetrable sentence to give
up. Added `no_runaway_sentence`, an absolute per-sentence ceiling.

**2. An unfixable check is worse than no check.** The first live run was rejected
three times on `jargon_density` while the lesson was defining its terms perfectly
well — the phrasing simply was not in the hand-curated synonym list. Because the
feedback said "define this term", the generator rewrote the definition, the regex
missed again, and the loop could not converge. Detection now matches the *form*
of a definition rather than guessing its wording, with depth left to the judged
check. See commit `41544b1`.

**3. An outage looked exactly like a working rubric.** A live `verify` run
reported *"every planted error was caught"* while the judge was returning 429 for
every call — nothing had been evaluated at all. With no evaluator running, every
check fails for every input, so each planted error is trivially "caught". Checks
that did not actually run are now marked `errored`, excluded from the caught set,
and void the run rather than decorating it; backoff is sized to the error so a
per-minute rate limit no longer poisons every remaining call. See commit
`c72be6d`.

**4. The anti-gaming defence became a rubber stamp.** Every judged failure had to
quote the offending text, and unquotable failures were discarded as fabricated.
That is right for a *presence* check (an idiom exists and can be quoted) and
exactly backwards for an *absence* check, where the failure is that content is
**missing** and there is nothing to quote. Against a lesson cut to a 50-word
stub, the judge correctly returned *"The lesson body is empty."* — the guard
ruled it fabricated and flipped the FAIL to a PASS. Two different live judges
then passed the stub on `has_worked_example` and `covers_what_why_how`. Checks
now declare `evidence_required`; the four absence checks are exempt.

The general form of the last two is the point of the whole project: **a
monitoring system that cannot tell "the thing is fine" from "the monitor is
broken" will eventually report that a broken thing is fine.** Both bugs made the
system confidently green while evaluating nothing, and both were caught only
because the evaluator is itself something we deliberately attack.

## Known limitations

Stated in full in [`ARCHITECTURE.md` § 16](ARCHITECTURE.md#16-what-this-design-gets-wrong).
The short version: one judge model is a single point of failure; thresholds are
defensible but not validated against real learners; directives accumulate and are
never automatically retired; and `verify` proves the rubric catches *these seven*
errors, not that it is complete.

## Note on models

The API key used for the recorded runs is a free-tier Google AI Studio key, on
which every pro-tier model returns 429 with zero quota and `gemini-2.5-pro`
returns 404. Defaults are therefore flash-tier (`gemini-3.6-flash` for generation
and judging). Nothing in the architecture depends on this — `lessonforge models`
lists what a given key can reach, and any model is a one-line `.env` change.
