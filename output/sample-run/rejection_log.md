# Rejection Log — Introduction to RAG (Retrieval-Augmented Generation)

- **Generated:** 2026-08-11T11:30:41+00:00
- **Provider / models:** gemini · gen `gemini-3.6-flash` · judge `gemini-3.6-flash`
- **Attempts used:** 3 (max 3)
- **Final outcome:** SHIPPED
- **Learned directives applied from memory:** 0

---

## Attempt 1 — REJECTED

`1391 words · 106 sentences · avg 13.12 words/sentence · Flesch-Kincaid grade 8.68`

17/18 checks passed

| Check | Dimension | Type | Result |
| --- | --- | --- | --- |
| `accuracy_grounded` | accurate_grounded | judged | PASS |
| `no_unsupported_claims` | accurate_grounded | judged | PASS |
| `no_weight_update_myth` | accurate_grounded | judged | PASS |
| `readability_grade` | beginner_language | deterministic | PASS |
| `sentence_length` | beginner_language | deterministic | PASS |
| `no_runaway_sentence` | beginner_language | deterministic | **FAIL** |
| `no_idioms_or_cultural_refs` | beginner_language | judged | PASS |
| `has_concrete_analogy` | teaches_by_example | judged | PASS |
| `has_worked_example` | teaches_by_example | judged | PASS |
| `example_density` | teaches_by_example | deterministic | PASS |
| `jargon_defined_on_first_use` | no_unexplained_jargon | judged | PASS |
| `jargon_density` | no_unexplained_jargon | deterministic | PASS |
| `covers_what_why_how` | covers_key_points | judged | PASS |
| `covers_three_steps` | covers_key_points | deterministic | PASS |
| `no_forward_references` | coherent_flow | judged | PASS |
| `standalone_completeness` | coherent_flow | judged | PASS |
| `has_recap` | coherent_flow | judged | PASS |
| `length_in_range` | beginner_language | deterministic | PASS |

### Why it was rejected (1 blocking failures)

**`no_runaway_sentence` — No single sentence exceeds the absolute hard cap**

- *Reason:* 2 sentence(s) exceed the absolute limit of 45 words. The longest is 51 words. A reader in their second language cannot hold a sentence this long.
- *Evidence from the draft:* “If the answer is not in the context, say "I do not know." Context: "Under the Shubh Griha scheme launched in January 2024, the annual interest rate for home loans is set at 8.5% for loans up to 30 lakhs." Question: What is the interest rate for the Shubh Griha home loan scheme in 2024?”
- *Required fix:* Find the longest sentence and break it into three or four short ones.

### What changed going into attempt 2

The failures above were fed back to the generator as a structured revision brief — the failing check, the reason, the quoted offending text, and the required fix — with an instruction to preserve everything that was not flagged.

- **Still failing:** `no_runaway_sentence`
- **Newly broken (regression):** `jargon_density`

---

## Attempt 2 — REJECTED

`1372 words · 106 sentences · avg 12.94 words/sentence · Flesch-Kincaid grade 8.64`

16/18 checks passed

| Check | Dimension | Type | Result |
| --- | --- | --- | --- |
| `accuracy_grounded` | accurate_grounded | judged | PASS |
| `no_unsupported_claims` | accurate_grounded | judged | PASS |
| `no_weight_update_myth` | accurate_grounded | judged | PASS |
| `readability_grade` | beginner_language | deterministic | PASS |
| `sentence_length` | beginner_language | deterministic | PASS |
| `no_runaway_sentence` | beginner_language | deterministic | **FAIL** |
| `no_idioms_or_cultural_refs` | beginner_language | judged | PASS |
| `has_concrete_analogy` | teaches_by_example | judged | PASS |
| `has_worked_example` | teaches_by_example | judged | PASS |
| `example_density` | teaches_by_example | deterministic | PASS |
| `jargon_defined_on_first_use` | no_unexplained_jargon | judged | PASS |
| `jargon_density` | no_unexplained_jargon | deterministic | **FAIL** |
| `covers_what_why_how` | covers_key_points | judged | PASS |
| `covers_three_steps` | covers_key_points | deterministic | PASS |
| `no_forward_references` | coherent_flow | judged | PASS |
| `standalone_completeness` | coherent_flow | judged | PASS |
| `has_recap` | coherent_flow | judged | PASS |
| `length_in_range` | beginner_language | deterministic | PASS |

### Why it was rejected (2 blocking failures)

**`no_runaway_sentence` — No single sentence exceeds the absolute hard cap**

- *Reason:* 1 sentence(s) exceed the absolute limit of 45 words. The longest is 56 words. A reader in their second language cannot hold a sentence this long.
- *Evidence from the draft:* “It finds the single most relevant chunk from an internal bank PDF: Found Chunk: "Under the Shubh Griha scheme launched in January 2024, the home loan interest rate is 8.5% for loans up to 30 lakhs." The system pastes the retrieved chunk into the prompt sent to the LLM: System Instruction: Answer the question using only the context below.”
- *Required fix:* Find the longest sentence and break it into three or four short ones.

**`jargon_density` — No known technical term appears without a nearby definition**

- *Reason:* These technical terms are used without a plain-English definition nearby: hallucination.
- *Evidence from the draft:* “hallucination: …personal notes, or private reports.  Third, an LLM can suffer from **hallucination**. A **hallucination** happens when an LLM gives a confident answer t…”
- *Required fix:* For each flagged term, add a short definition within one sentence of its first appearance.

### What changed going into attempt 3

The failures above were fed back to the generator as a structured revision brief — the failing check, the reason, the quoted offending text, and the required fix — with an instruction to preserve everything that was not flagged.

- **Fixed:** `jargon_density`, `no_runaway_sentence`

---

## Attempt 3 — PASSED — shippable

`1495 words · 120 sentences · avg 12.46 words/sentence · Flesch-Kincaid grade 8.8`

18/18 checks passed

| Check | Dimension | Type | Result |
| --- | --- | --- | --- |
| `accuracy_grounded` | accurate_grounded | judged | PASS |
| `no_unsupported_claims` | accurate_grounded | judged | PASS |
| `no_weight_update_myth` | accurate_grounded | judged | PASS |
| `readability_grade` | beginner_language | deterministic | PASS |
| `sentence_length` | beginner_language | deterministic | PASS |
| `no_runaway_sentence` | beginner_language | deterministic | PASS |
| `no_idioms_or_cultural_refs` | beginner_language | judged | PASS |
| `has_concrete_analogy` | teaches_by_example | judged | PASS |
| `has_worked_example` | teaches_by_example | judged | PASS |
| `example_density` | teaches_by_example | deterministic | PASS |
| `jargon_defined_on_first_use` | no_unexplained_jargon | judged | PASS |
| `jargon_density` | no_unexplained_jargon | deterministic | PASS |
| `covers_what_why_how` | covers_key_points | judged | PASS |
| `covers_three_steps` | covers_key_points | deterministic | PASS |
| `no_forward_references` | coherent_flow | judged | PASS |
| `standalone_completeness` | coherent_flow | judged | PASS |
| `has_recap` | coherent_flow | judged | PASS |
| `length_in_range` | beginner_language | deterministic | PASS |

All blocking checks passed.


---

## Outcome

The lesson passed every blocking check on attempt 3 and was written to `lesson.md`.

## What the system learned from this run

These directives were added to the generator's standing instructions and will apply to every future run, before the first attempt:

- (`no_runaway_sentence`) Never write any sentence that exceeds 40 words; split longer thoughts into multiple concise sentences.
