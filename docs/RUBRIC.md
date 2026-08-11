# Rubric

Every check is hard pass/fail. There is no partial credit and no
weighted score. A lesson ships only if **every blocking check passes**.

| # | Check | Dimension | Engine | Blocking | What it tests |
| --- | --- | --- | --- | --- | --- |
| 1 | `accuracy_grounded` | accurate_grounded | judged | yes | Every factual claim matches the grounding source |
| 2 | `no_unsupported_claims` | accurate_grounded | judged | yes | No invented specifics beyond the grounding source |
| 3 | `no_weight_update_myth` | accurate_grounded | judged | yes | Does not imply RAG retrains or modifies the model |
| 4 | `readability_grade` | beginner_language | deterministic | yes | Flesch-Kincaid grade level within beginner range |
| 5 | `sentence_length` | beginner_language | deterministic | yes | Average and worst-case sentence length are readable |
| 6 | `no_runaway_sentence` | beginner_language | deterministic | yes | No single sentence exceeds the absolute hard cap |
| 7 | `no_idioms_or_cultural_refs` | beginner_language | judged | yes | No idioms, slang, or culture-specific references |
| 8 | `has_concrete_analogy` | teaches_by_example | judged | yes | Explains the core idea with an everyday analogy |
| 9 | `has_worked_example` | teaches_by_example | judged | yes | Traces one concrete question end to end |
| 10 | `example_density` | teaches_by_example | deterministic | yes | Contains enough explicit example/analogy signposting |
| 11 | `jargon_defined_on_first_use` | no_unexplained_jargon | judged | yes | Every technical term is defined where it first appears |
| 12 | `jargon_density` | no_unexplained_jargon | deterministic | yes | No known technical term appears without a nearby definition |
| 13 | `covers_what_why_how` | covers_key_points | judged | yes | Covers what RAG is, why it matters, and how it works |
| 14 | `covers_three_steps` | covers_key_points | deterministic | yes | Names all three pipeline stages explicitly |
| 15 | `no_forward_references` | coherent_flow | judged | yes | Never relies on a concept before explaining it |
| 16 | `standalone_completeness` | coherent_flow | judged | yes | Self-contained: no external or prior-lesson dependencies |
| 17 | `has_recap` | coherent_flow | judged | advisory | Ends with a recap or summary (advisory) |
| 18 | `length_in_range` | beginner_language | deterministic | advisory | Word count within target range (advisory) |

## Check definitions

### `accuracy_grounded`

- **Dimension:** accurate_grounded
- **Engine:** judged
- **Blocking:** yes
- **Tests:** Every factual claim matches the grounding source
- **Question put to the evaluator:** Does every technical claim in the lesson agree with the GROUND TRUTH document? Answer FAIL if the lesson asserts anything that contradicts a numbered FACT, or anything listed under 'Forbidden claims'.
- **Remediation hint fed back on retry:** Rewrite the offending sentence so it matches the ground truth exactly. Do not soften it — delete or correct it.

### `no_unsupported_claims`

- **Dimension:** accurate_grounded
- **Engine:** judged
- **Blocking:** yes
- **Tests:** No invented specifics beyond the grounding source
- **Question put to the evaluator:** Does the lesson invent specific numbers, benchmarks, dates, company claims, or performance figures that do not appear in the GROUND TRUTH? Generic illustrative examples are fine; fabricated precision is not. Answer FAIL if any invented specific is stated as fact.
- **Remediation hint fed back on retry:** Remove the invented figure, or rephrase it as an illustration ('for example, imagine 3 chunks') rather than a fact.

### `no_weight_update_myth`

- **Dimension:** accurate_grounded
- **Engine:** judged
- **Blocking:** yes
- **Tests:** Does not imply RAG retrains or modifies the model
- **Question put to the evaluator:** Does the lesson state or imply that RAG trains, retrains, fine-tunes, updates the weights of, or permanently stores documents inside the model? Answer FAIL if it does, even implicitly (e.g. 'the model learns your documents'). See FACT-08.
- **Remediation hint fed back on retry:** State explicitly that the retrieved text is placed in the prompt for that one question only and the model itself never changes.

### `readability_grade`

- **Dimension:** beginner_language
- **Engine:** deterministic
- **Blocking:** yes
- **Tests:** Flesch-Kincaid grade level within beginner range
- **Question put to the evaluator:** Is the computed Flesch-Kincaid grade level at or below the threshold?
- **Remediation hint fed back on retry:** Shorten sentences and swap multi-syllable words for everyday ones. Prefer 'uses' over 'utilises', 'find' over 'ascertain'.

### `sentence_length`

- **Dimension:** beginner_language
- **Engine:** deterministic
- **Blocking:** yes
- **Tests:** Average and worst-case sentence length are readable
- **Question put to the evaluator:** Is the average sentence short enough, with few very long sentences?
- **Remediation hint fed back on retry:** Split every sentence that runs past ~25 words into two. One idea per sentence.

### `no_runaway_sentence`

- **Dimension:** beginner_language
- **Engine:** deterministic
- **Blocking:** yes
- **Tests:** No single sentence exceeds the absolute hard cap
- **Question put to the evaluator:** Is every sentence below the absolute maximum length?
- **Remediation hint fed back on retry:** Find the longest sentence and break it into three or four short ones.

### `no_idioms_or_cultural_refs`

- **Dimension:** beginner_language
- **Engine:** judged
- **Blocking:** yes
- **Tests:** No idioms, slang, or culture-specific references
- **Question put to the evaluator:** Does the lesson use English idioms, phrasal slang, sports metaphors, or culture-specific references that a reader from a non-English-medium background in India would likely not know? Examples that would FAIL: 'out of the box', 'ballpark figure', 'home run', 'piece of cake', 'silver bullet', 'boils down to'. Answer FAIL if any appear.
- **Remediation hint fed back on retry:** Replace the idiom with plain literal wording. 'Out of the box' becomes 'without extra setup'.

### `has_concrete_analogy`

- **Dimension:** teaches_by_example
- **Engine:** judged
- **Blocking:** yes
- **Tests:** Explains the core idea with an everyday analogy
- **Question put to the evaluator:** Does the lesson explain what RAG is using at least one concrete, everyday analogy drawn from ordinary life (e.g. an open-book exam, a librarian, a cookbook)? A restatement in technical words is not an analogy. Answer FAIL if no such analogy is present.
- **Remediation hint fed back on retry:** Add one everyday analogy early in the lesson and carry it through, mapping each part of the analogy to a part of RAG.

### `has_worked_example`

- **Dimension:** teaches_by_example
- **Engine:** judged
- **Blocking:** yes
- **Tests:** Traces one concrete question end to end
- **Question put to the evaluator:** Does the lesson walk through at least one specific example question from start to finish — showing what gets retrieved, what the prompt then contains, and what the model answers? A list of the three steps in the abstract is NOT a worked example. Answer FAIL if no single question is traced through all three steps.
- **Remediation hint fed back on retry:** Pick one realistic question, then show the retrieved chunk text, the assembled prompt, and the final answer as separate labelled blocks.

### `example_density`

- **Dimension:** teaches_by_example
- **Engine:** deterministic
- **Blocking:** yes
- **Tests:** Contains enough explicit example/analogy signposting
- **Question put to the evaluator:** Does the text contain the minimum number of example and analogy markers?
- **Remediation hint fed back on retry:** Signpost your examples explicitly with phrases like 'For example,' or 'Think of it like'. Readers skim for these.

### `jargon_defined_on_first_use`

- **Dimension:** no_unexplained_jargon
- **Engine:** judged
- **Blocking:** yes
- **Tests:** Every technical term is defined where it first appears
- **Question put to the evaluator:** Take every technical term in the lesson (embedding, vector, chunk, index, token, LLM, semantic, top-k, cosine similarity, fine-tuning, prompt, corpus, latency, inference, hallucination). Is each one given a plain-English definition at or before its first use? Answer FAIL if any term is used before it is explained.
- **Remediation hint fed back on retry:** Define the term in the same sentence where it first appears, in plain words, before using it again.

### `jargon_density`

- **Dimension:** no_unexplained_jargon
- **Engine:** deterministic
- **Blocking:** yes
- **Tests:** No known technical term appears without a nearby definition
- **Question put to the evaluator:** Is the count of undefined technical terms at or below the threshold?
- **Remediation hint fed back on retry:** For each flagged term, add a short definition within one sentence of its first appearance.

### `covers_what_why_how`

- **Dimension:** covers_key_points
- **Engine:** judged
- **Blocking:** yes
- **Tests:** Covers what RAG is, why it matters, and how it works
- **Question put to the evaluator:** Does the lesson substantively cover all three of: (a) WHAT RAG is, (b) WHY it matters — the concrete problems it solves, (c) HOW it works — the retrieve, augment, generate pipeline? All three must be present and explained, not merely mentioned. Answer FAIL if any is missing or reduced to a single passing sentence.
- **Remediation hint fed back on retry:** Add a dedicated section for whichever of what/why/how is thin, with at least a full paragraph of real explanation.

### `covers_three_steps`

- **Dimension:** covers_key_points
- **Engine:** deterministic
- **Blocking:** yes
- **Tests:** Names all three pipeline stages explicitly
- **Question put to the evaluator:** Do the words retrieve, augment, and generate all appear?
- **Remediation hint fed back on retry:** Name the three stages using the actual words Retrieve, Augment, and Generate so the reader can connect them to the acronym.

### `no_forward_references`

- **Dimension:** coherent_flow
- **Engine:** judged
- **Blocking:** yes
- **Tests:** Never relies on a concept before explaining it
- **Question put to the evaluator:** Reading strictly top to bottom, does the lesson ever depend on a concept it has not yet introduced — including phrases like 'as we will see later' used to defer a definition the reader needs now? Answer FAIL if the reader would be stuck at any point.
- **Remediation hint fed back on retry:** Reorder so each concept is fully introduced before it is used. Move the definition up rather than promising it later.

### `standalone_completeness`

- **Dimension:** coherent_flow
- **Engine:** judged
- **Blocking:** yes
- **Tests:** Self-contained: no external or prior-lesson dependencies
- **Question put to the evaluator:** Does the lesson assume the reader has seen an earlier lesson, a video, a course, or an external link in order to follow it? Phrases like 'as discussed previously' or 'recall from module 2' FAIL. Answer FAIL if the lesson is not fully self-contained.
- **Remediation hint fed back on retry:** Remove references to outside material and inline whatever context the reader needs.

### `has_recap`

- **Dimension:** coherent_flow
- **Engine:** judged
- **Blocking:** no (advisory)
- **Tests:** Ends with a recap or summary (advisory)
- **Question put to the evaluator:** Does the lesson end with a short recap, summary, or 'what you learned' section that restates the key points?
- **Remediation hint fed back on retry:** Add a 5-point recap at the end.

### `length_in_range`

- **Dimension:** beginner_language
- **Engine:** deterministic
- **Blocking:** no (advisory)
- **Tests:** Word count within target range (advisory)
- **Question put to the evaluator:** Is the word count between the configured minimum and maximum?
- **Remediation hint fed back on retry:** Expand thin sections or cut repetition to land in range.
