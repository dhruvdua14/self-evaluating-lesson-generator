"""The rubric: 15 hard pass/fail checkpoints.

Two rules govern every entry here:

1. **A check must be answerable yes/no by someone who only reads the lesson.**
   If answering it needs the generation prompt or the author's intent, it is not
   a check, it is a vibe.

2. **A check must be cheap to disagree with.** Every judged check demands a
   verbatim quote as evidence. If the judge cannot quote the problem, there is
   no problem.

Anything that cannot be settled by reading the text — "is this engaging?" — is
deliberately excluded. Engagement is real but unfalsifiable, and an
unfalsifiable check silently becomes a rubber stamp.
"""

from __future__ import annotations

from .schema import CheckKind, CheckSpec, Dimension

D = Dimension
K = CheckKind

RUBRIC: tuple[CheckSpec, ...] = (
    # ---------------------------------------------------------------- accuracy
    CheckSpec(
        id="accuracy_grounded",
        dimension=D.ACCURATE_GROUNDED,
        kind=K.JUDGED,
        blocking=True,
        title="Every factual claim matches the grounding source",
        question=(
            "Does every technical claim in the lesson agree with the GROUND TRUTH "
            "document? Answer FAIL if the lesson asserts anything that contradicts "
            "a numbered FACT, or anything listed under 'Forbidden claims'."
        ),
        remediation_hint=(
            "Rewrite the offending sentence so it matches the ground truth exactly. "
            "Do not soften it — delete or correct it."
        ),
    ),
    CheckSpec(
        id="no_unsupported_claims",
        dimension=D.ACCURATE_GROUNDED,
        kind=K.JUDGED,
        blocking=True,
        title="No invented specifics beyond the grounding source",
        question=(
            "Does the lesson invent specific numbers, benchmarks, dates, company "
            "claims, or performance figures that do not appear in the GROUND TRUTH? "
            "Generic illustrative examples are fine; fabricated precision is not. "
            "Answer FAIL if any invented specific is stated as fact."
        ),
        remediation_hint=(
            "Remove the invented figure, or rephrase it as an illustration "
            "('for example, imagine 3 chunks') rather than a fact."
        ),
    ),
    CheckSpec(
        id="no_weight_update_myth",
        dimension=D.ACCURATE_GROUNDED,
        kind=K.JUDGED,
        blocking=True,
        title="Does not imply RAG retrains or modifies the model",
        question=(
            "Does the lesson state or imply that RAG trains, retrains, fine-tunes, "
            "updates the weights of, or permanently stores documents inside the "
            "model? Answer FAIL if it does, even implicitly (e.g. 'the model learns "
            "your documents'). See FACT-08."
        ),
        remediation_hint=(
            "State explicitly that the retrieved text is placed in the prompt for "
            "that one question only and the model itself never changes."
        ),
    ),
    # ------------------------------------------------------- beginner language
    CheckSpec(
        id="readability_grade",
        dimension=D.BEGINNER_LANGUAGE,
        kind=K.DETERMINISTIC,
        blocking=True,
        title="Flesch-Kincaid grade level within beginner range",
        question="Is the computed Flesch-Kincaid grade level at or below the threshold?",
        remediation_hint=(
            "Shorten sentences and swap multi-syllable words for everyday ones. "
            "Prefer 'uses' over 'utilises', 'find' over 'ascertain'."
        ),
    ),
    CheckSpec(
        id="sentence_length",
        dimension=D.BEGINNER_LANGUAGE,
        kind=K.DETERMINISTIC,
        blocking=True,
        title="Average and worst-case sentence length are readable",
        question="Is the average sentence short enough, with few very long sentences?",
        remediation_hint=(
            "Split every sentence that runs past ~25 words into two. One idea per "
            "sentence."
        ),
    ),
    CheckSpec(
        id="no_runaway_sentence",
        dimension=D.BEGINNER_LANGUAGE,
        kind=K.DETERMINISTIC,
        blocking=True,
        title="No single sentence exceeds the absolute hard cap",
        question="Is every sentence below the absolute maximum length?",
        remediation_hint=(
            "Find the longest sentence and break it into three or four short ones."
        ),
        # Added after evaluator verification showed that `readability_grade` and
        # `sentence_length` are document-level averages: appending one 60-word
        # unreadable paragraph to a long clean lesson moved the grade only
        # 4.67 -> 5.62, well inside the limit. Averages are robust to localised
        # damage, which is exactly the wrong property for a beginner reader who
        # only has to hit one impenetrable sentence to stop reading. This check
        # is the absolute floor that averages cannot provide.
    ),
    CheckSpec(
        id="no_idioms_or_cultural_refs",
        dimension=D.BEGINNER_LANGUAGE,
        kind=K.JUDGED,
        blocking=True,
        title="No idioms, slang, or culture-specific references",
        question=(
            "Does the lesson use English idioms, phrasal slang, sports metaphors, or "
            "culture-specific references that a reader from a non-English-medium "
            "background in India would likely not know? Examples that would FAIL: "
            "'out of the box', 'ballpark figure', 'home run', 'piece of cake', "
            "'silver bullet', 'boils down to'. Answer FAIL if any appear."
        ),
        remediation_hint=(
            "Replace the idiom with plain literal wording. 'Out of the box' becomes "
            "'without extra setup'."
        ),
    ),
    # ------------------------------------------------------ teaches by example
    CheckSpec(
        id="has_concrete_analogy",
        evidence_required=False,  # absence check: nothing to quote
        dimension=D.TEACHES_BY_EXAMPLE,
        kind=K.JUDGED,
        blocking=True,
        title="Explains the core idea with an everyday analogy",
        question=(
            "Does the lesson explain what RAG is using at least one concrete, "
            "everyday analogy drawn from ordinary life (e.g. an open-book exam, a "
            "librarian, a cookbook)? A restatement in technical words is not an "
            "analogy. Answer FAIL if no such analogy is present."
        ),
        remediation_hint=(
            "Add one everyday analogy early in the lesson and carry it through, "
            "mapping each part of the analogy to a part of RAG."
        ),
    ),
    CheckSpec(
        id="has_worked_example",
        evidence_required=False,  # absence check: nothing to quote
        dimension=D.TEACHES_BY_EXAMPLE,
        kind=K.JUDGED,
        blocking=True,
        title="Traces one concrete question end to end",
        question=(
            "Does the lesson walk through at least one specific example question "
            "from start to finish — showing what gets retrieved, what the prompt "
            "then contains, and what the model answers? A list of the three steps "
            "in the abstract is NOT a worked example. Answer FAIL if no single "
            "question is traced through all three steps."
        ),
        remediation_hint=(
            "Pick one realistic question, then show the retrieved chunk text, the "
            "assembled prompt, and the final answer as separate labelled blocks."
        ),
    ),
    CheckSpec(
        id="example_density",
        dimension=D.TEACHES_BY_EXAMPLE,
        kind=K.DETERMINISTIC,
        blocking=True,
        title="Contains enough explicit example/analogy signposting",
        question="Does the text contain the minimum number of example and analogy markers?",
        remediation_hint=(
            "Signpost your examples explicitly with phrases like 'For example,' or "
            "'Think of it like'. Readers skim for these."
        ),
    ),
    # ---------------------------------------------------------------- jargon
    CheckSpec(
        id="jargon_defined_on_first_use",
        dimension=D.NO_UNEXPLAINED_JARGON,
        kind=K.JUDGED,
        blocking=True,
        title="Every technical term is defined where it first appears",
        question=(
            "Take every technical term in the lesson (embedding, vector, chunk, "
            "index, token, LLM, semantic, top-k, cosine similarity, fine-tuning, "
            "prompt, corpus, latency, inference, hallucination). Is each one given "
            "a plain-English definition at or before its first use? Answer FAIL if "
            "any term is used before it is explained."
        ),
        remediation_hint=(
            "Define the term in the same sentence where it first appears, in plain "
            "words, before using it again."
        ),
    ),
    CheckSpec(
        id="jargon_density",
        dimension=D.NO_UNEXPLAINED_JARGON,
        kind=K.DETERMINISTIC,
        blocking=True,
        title="No known technical term appears without a nearby definition",
        question="Is the count of undefined technical terms at or below the threshold?",
        remediation_hint=(
            "For each flagged term, add a short definition within one sentence of "
            "its first appearance."
        ),
    ),
    # ----------------------------------------------------------- key coverage
    CheckSpec(
        id="covers_what_why_how",
        evidence_required=False,  # absence check: nothing to quote
        dimension=D.COVERS_KEY_POINTS,
        kind=K.JUDGED,
        blocking=True,
        title="Covers what RAG is, why it matters, and how it works",
        question=(
            "Does the lesson substantively cover all three of: (a) WHAT RAG is, "
            "(b) WHY it matters — the concrete problems it solves, (c) HOW it works "
            "— the retrieve, augment, generate pipeline? All three must be present "
            "and explained, not merely mentioned. Answer FAIL if any is missing or "
            "reduced to a single passing sentence."
        ),
        remediation_hint=(
            "Add a dedicated section for whichever of what/why/how is thin, with at "
            "least a full paragraph of real explanation."
        ),
    ),
    CheckSpec(
        id="covers_three_steps",
        dimension=D.COVERS_KEY_POINTS,
        kind=K.DETERMINISTIC,
        blocking=True,
        title="Names all three pipeline stages explicitly",
        question="Do the words retrieve, augment, and generate all appear?",
        remediation_hint=(
            "Name the three stages using the actual words Retrieve, Augment, and "
            "Generate so the reader can connect them to the acronym."
        ),
    ),
    # ------------------------------------------------------------------- flow
    CheckSpec(
        id="no_forward_references",
        dimension=D.COHERENT_FLOW,
        kind=K.JUDGED,
        blocking=True,
        title="Never relies on a concept before explaining it",
        question=(
            "Reading strictly top to bottom, does the lesson ever depend on a "
            "concept it has not yet introduced — including phrases like 'as we will "
            "see later' used to defer a definition the reader needs now? Answer FAIL "
            "if the reader would be stuck at any point."
        ),
        remediation_hint=(
            "Reorder so each concept is fully introduced before it is used. Move the "
            "definition up rather than promising it later."
        ),
    ),
    CheckSpec(
        id="standalone_completeness",
        dimension=D.COHERENT_FLOW,
        kind=K.JUDGED,
        blocking=True,
        title="Self-contained: no external or prior-lesson dependencies",
        question=(
            "Does the lesson assume the reader has seen an earlier lesson, a video, "
            "a course, or an external link in order to follow it? Phrases like 'as "
            "discussed previously' or 'recall from module 2' FAIL. Answer FAIL if "
            "the lesson is not fully self-contained."
        ),
        remediation_hint=(
            "Remove references to outside material and inline whatever context the "
            "reader needs."
        ),
    ),
    # -------------------------------------------------------------- advisory
    # Non-blocking. Tracked in every report so quality drift is visible, but a
    # failure here does NOT stop the lesson shipping. Keeping a couple of checks
    # advisory is what stops the rubric becoming a wall the loop can never clear.
    CheckSpec(
        id="has_recap",
        evidence_required=False,  # absence check: nothing to quote
        dimension=D.COHERENT_FLOW,
        kind=K.JUDGED,
        blocking=False,
        title="Ends with a recap or summary (advisory)",
        question=(
            "Does the lesson end with a short recap, summary, or 'what you learned' "
            "section that restates the key points?"
        ),
        remediation_hint="Add a 5-point recap at the end.",
    ),
    CheckSpec(
        id="length_in_range",
        dimension=D.BEGINNER_LANGUAGE,
        kind=K.DETERMINISTIC,
        blocking=False,
        title="Word count within target range (advisory)",
        question="Is the word count between the configured minimum and maximum?",
        remediation_hint="Expand thin sections or cut repetition to land in range.",
    ),
)

BY_ID: dict[str, CheckSpec] = {c.id: c for c in RUBRIC}
DETERMINISTIC_CHECKS = tuple(c for c in RUBRIC if c.kind is CheckKind.DETERMINISTIC)
JUDGED_CHECKS = tuple(c for c in RUBRIC if c.kind is CheckKind.JUDGED)
BLOCKING_IDS = frozenset(c.id for c in RUBRIC if c.blocking)


def spec(check_id: str) -> CheckSpec:
    return BY_ID[check_id]
