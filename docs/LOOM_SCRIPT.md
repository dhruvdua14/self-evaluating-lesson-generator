# Loom recording script (15–20 min)

Face visible throughout. Terminal + editor side by side, font size up.

**Before you hit record:**

```bash
cd <repo>
make test                      # confirm 61 green
cp .env.example .env           # GEMINI_API_KEY set
rm -rf output/2*               # clean slate for the demo
lessonforge memory --reset     # so the memory story starts from zero
clear
```

Keep two terminal tabs open: one for commands, one already sitting in the repo
for showing files.

---

## 0 · Framing (0:00–1:30)

> "The brief asks for a system that generates a lesson and judges its own
> quality. I want to start by saying which half I think is the hard half.
>
> Generating a beginner lesson is easy — any decent model does that in one
> prompt. The hard problem is deciding whether the lesson is good enough to put
> in front of a learner, **without a human reading it**. So the generator is the
> least interesting component in what I built. The evaluator is the product, and
> most of my design effort went into making the evaluator trustworthy — and into
> proving it is."

Then name the learner:

> "The target reader is specific: a 12th-grade graduate from India, limited
> English vocabulary, non-English-medium schooling, starting from zero. That
> specificity is what makes a rubric possible at all. 'Is this
> beginner-friendly?' is unanswerable. 'Would *this* reader be stopped by this
> sentence?' is answerable — and several of my checks fall straight out of it."

---

## 1 · The rubric (1:30–4:00)

```bash
lessonforge rubric
```

> "Eighteen checkpoints across the six dimensions in the brief. Sixteen block
> shipping, two are advisory."

Make three points, in this order:

**Hard pass/fail, no scores.** Open `src/lessonforge/rubric/schema.py`.

> "Every check returns PASS or FAIL. There is no numeric score anywhere in the
> data model — there's a test that asserts no field called `score` or
> `confidence` exists. A score invites a threshold argument: is 7.5 good enough?
> That argument never resolves. Worse, a model that can say '7 out of 10' will
> say that instead of committing. A boolean forces a decision. And averaging
> hides exactly the failures that matter most — a lesson that's excellent on five
> dimensions and factually wrong on the sixth scores well and must never ship."

**Two engines.** Point at the `engine` column.

> "Half these checks never call a model. Readability, sentence length, jargon
> density — those are counting problems, and LLMs cannot reliably count. So I
> measure them in Python. Same draft, same verdict, forever, at zero cost. And
> the generator can't talk a regex out of its verdict."

**Where the audience shows up.** Point at `no_idioms_or_cultural_refs`.

> "This one exists purely because of who the reader is. 'Out of the box', 'home
> run', 'ballpark' — a model writes those constantly and this reader doesn't know
> them."

---

## 2 · The architecture (4:00–7:00)

```bash
lessonforge graph
```

Then open `src/lessonforge/graph.py` and scroll to `add_conditional_edges`.

> "That single conditional edge is the entire self-correction loop. Fail with
> budget left, go back to generate. Otherwise move on."

Scroll up to `gate`.

> "Termination lives in exactly one place, and it's a **pure function** — no I/O,
> no model call. Which means I can unit-test it, and I do, across six cases
> including one where I set max_retries to 9999 and assert the loop still stops,
> because there's an independent hard cap."

Then the two decisions worth defending:

**Planner separate from generator.**

> "One call decides what to teach and in what order. A second decides how to word
> it. So when a lesson fails on sentence length, I don't re-derive the
> curriculum — the retry is a targeted repair, not a re-roll."

**Judge independence.** Open `src/lessonforge/rubric/judge.py`, read the module
docstring aloud.

> "The judge gets three things: the lesson, the ground truth, the checklist. It
> never sees the generation prompt, the plan, or the attempt number. A model shown
> 'here's what you were asked to write and here's what you wrote' grades its own
> homework, and grades it kindly. I remove the authorship cue. It reads an
> anonymous document, exactly like a learner would.
>
> I also withhold the attempt number deliberately — an evaluator that knows this
> is the last attempt has a reason to go easy."

---

## 3 · The loop running end to end (7:00–11:00)

```bash
lessonforge run
```

Let it run live. Narrate as events appear:

- **plan** — "blueprint, concept order, the analogy it picked."
- **generate attempt 1** — "first draft, no feedback yet."
- **evaluate** — read out two or three actual failures. *"It failed its own
  first draft, and it's telling me exactly which sentence and why."*
- **generate attempt 2** — "note the tag: with revision brief."
- **evaluate** — pass.
- **gate** — shipped.

Then open the rejection log:

```bash
cat output/2*/rejection_log.md
```

> "This is the artefact I'd actually defend in a review. Anyone can show you a
> good final lesson. This shows the system rejecting its own work — every failed
> check, the reason, the **quoted offending text**, and a diff of what the retry
> fixed versus what it didn't."

Scroll to a "What changed going into attempt 2" section and read the Fixed line.

Then show the feedback construction — `nodes/generate.py`, `build_feedback`:

> "The revision brief is structured, not a complaint. Failing check, reason,
> quoted text, required fix — plus 'keep everything not flagged'. 'Make it
> simpler' produces a differently-bad lesson. 'This 44-word sentence uses four
> undefined terms' produces a fix. And I deliberately don't list what passed,
> because that invites the model to rewrite things that were already fine."

---

## 4 · Catching a deliberate error (11:00–14:30)

This is the section the brief explicitly asks for. Do the strong version.

> "Obvious challenge to any self-evaluating system: it passed the lesson, but
> would it have failed a bad one? Let me not assert that — let me run the
> experiment."

```bash
lessonforge verify --judge-model gemini-3.1-flash-lite
```

> **Use the lite judge for this command on camera.** `verify` fires 7 judge
> calls back to back and will blow through a free-tier per-minute limit on the
> default model. The lite model draws from a separate pool and catches all six
> injections. If you hit the limit anyway, the run reports *Partially
> inconclusive* rather than a false green — which is itself worth showing, and
> is covered in the bug story below.

While it runs:

> "It takes a lesson that passes all sixteen blocking checks, confirms that
> first — if the baseline doesn't pass, the experiment is void and it says so —
> then corrupts it six different ways. And for each one I declared **in advance**,
> in `inject.py`, which checks must fail."

Show the results table. Then open `src/lessonforge/inject.py` and show the
`factual` injection payload.

> "That's the single most common beginner misconception about RAG — that it
> retrains the model. I plant it, and `no_weight_update_myth` fires."

Optionally show it inside a full run:

```bash
lessonforge run --inject-error factual --max-retries 1
```

**Then tell the bug story — this is the strongest 90 seconds in the video.**

> "This process found a real bug in my own rubric. I originally predicted the
> jargon injection would fail `readability_grade`. It didn't. When I appended one
> sixty-word unreadable paragraph to a long clean lesson, the Flesch-Kincaid
> grade moved from 4.67 to 5.62 — well inside my limit.
>
> The check wasn't wrong. My prediction was. A document-level average is
> *supposed* to survive one bad paragraph. But that robustness is exactly the
> wrong property for this reader, who only has to hit one impenetrable sentence
> to give up. So I added `no_runaway_sentence` — an absolute per-sentence ceiling
> that no averaging can smooth over — with a test that builds the exact case
> where every average passes and that check still fires.
>
> A rubric nobody has tried to fool is a rubric nobody knows works."

**Then the second bug story — this one is stronger, and it's the one to land if
you only have time for one.**

> "There's a second one, and it's the one I'm actually glad I found.
>
> On a live run, this verification printed 'every planted error was caught' —
> all green. It was completely wrong. The judge had hit its rate limit and was
> returning 429 for every single call. Nothing had been evaluated at all.
>
> Here's why it looked green. When every judge call fails, the system correctly
> records every check as failed — failing closed is the right behaviour. But
> then verification compared 'checks that failed' against 'checks I predicted
> would fail', found them all present, and concluded every injection was caught.
> An outage was indistinguishable from a perfectly discriminating rubric.
>
> So a check now carries a flag for 'this didn't actually run'. It still counts
> as a failure — I still fail closed — but it's no longer treated as *evidence
> about the content*. Those rows show as n/a, and if the baseline never
> evaluated, the whole run is voided instead of reported.
>
> The root cause was mine too: I had one backoff curve capped at 8 seconds for
> every retryable error. A per-minute rate limit is never going to clear in 8
> seconds, so once I hit it, every remaining call failed. Backoff is now sized to
> the error, and honours the server's own retry delay when it sends one.
>
> The general version of that is what I'd want a reviewer to take away: a
> monitoring system that can't tell 'the thing is fine' from 'the monitor is
> broken' will eventually tell you a broken thing is fine."

Show `tests/test_injection.py::test_rate_limited_evaluator_never_reports_success`
— it drives the whole verification with a provider that only ever raises 429 and
asserts the report comes back void.

---

## 5 · Memory and self-evolution (14:30–17:30)

```bash
lessonforge memory
```

> "Memory here doesn't mean conversation history. It answers one question across
> the system's lifetime: which checks does the generator keep failing, and what
> should I tell it up front so it stops?"

Walk the tables: failure patterns → learned directives → run history.

> "A check that fails twice across separate runs becomes a candidate. A reflector
> writes one imperative sentence, and that sentence gets injected into the
> generator's system prompt on every future run — **before the first attempt**,
> not as a retry fix."

If you have several runs recorded, point at the history table:

> "And here's the claim I'm making, deliberately narrow so it can be falsified:
> first-attempt pass rate should rise as directives accumulate. That number is
> printed right here. If it doesn't move, this layer is decoration — and this
> table is what proves it either way."

**Then the guard rail — say this explicitly:**

> "One thing I deliberately did **not** build: the system never edits its own
> rubric. It can tighten the writer; it can never lower the bar. If a check stops
> discriminating, it gets reported to a human. A loop allowed to relax its own
> passing criteria converges on passing everything — which is precisely the
> failure this whole system exists to prevent."

Show `memory/evolve.py` briefly — the check-id whitelist and the cap.

---

## 6 · Tests and honesty (17:30–19:30)

```bash
make test
```

> "Sixty-one tests, no API key needed — the whole loop runs offline against a
> deterministic provider that replays a genuinely bad draft and a genuinely good
> one through the real rubric."

Call out two tests by name:

- `test_missing_verdict_is_treated_as_failure` — *"if the judge skips a check, I
  record a failure, not a pass. Silence must never be a route to shipping."*
- `test_failure_with_fabricated_evidence_is_downgraded_to_pass` — *"every judged
  failure has to quote the lesson verbatim. If the quote isn't actually in the
  text, I throw the failure away. The judge can't invent a violation it can't
  cite."*

Then close on limitations — open `docs/ARCHITECTURE.md` § "What this design gets
wrong":

> "I wrote down what this gets wrong. One judge model is a single point of
> failure. My thresholds are defensible but not validated against real learners.
> Directives accumulate and are never automatically retired. And `verify` proves
> the rubric catches *these six* errors — it does not prove the rubric is
> complete. Nothing could."

---

## 7 · Close (19:30–20:00)

> "So: generate, evaluate against sixteen blocking hard-fail checks, feed the
> quoted failures back, regenerate, and refuse to ship if it still doesn't clear
> the bar. Plus a memory layer that makes the next run start better than this one
> did.
>
> The thing I'd want you to take from this is the evaluator, not the lesson —
> and specifically that I tried to break it before showing it to you."

---

## If a live run fails on camera

Don't cut. Say:

> "That's the fail-closed path — it just refused to ship something it judged
> inadequate. That's the designed behaviour, not a crash."

Then `cat output/2*/rejection_log.md` and walk the reasons. A live rejection is a
**better** demo than a clean pass, because it shows the gate has teeth. Keep
`--provider mock` ready as a fallback if the API is down.
