"""Deterministic rubric checks — pure Python, zero API calls.

Why half the rubric is not an LLM
---------------------------------
An LLM judge is the only way to assess meaning, but it is a poor instrument for
anything measurable. It cannot reliably count, it drifts between runs, and it
can be argued with. Readability, sentence length, jargon density and word count
are all *measurable*, so they are measured. That buys three things:

* **Reproducibility** — same draft, same verdict, forever.
* **Cost** — these run in microseconds and catch the most common beginner-content
  failures before a single token is spent on the judge.
* **Non-negotiability** — the generator cannot talk a regex out of its verdict.

Everything here is implemented from scratch rather than pulled from `textstat`
so the numbers are auditable and the package has no surprise dependency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import ReadabilityThresholds
from .schema import CheckKind, CheckResult

# Markdown scaffolding that would otherwise skew sentence and word statistics.
_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`]*`")
_MD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+.*$", re.MULTILINE)
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_EMPHASIS = re.compile(r"[*_]{1,3}([^*_]+)[*_]{1,3}")
_MD_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+", re.MULTILINE)
_MD_TABLE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_MD_QUOTE = re.compile(r"^\s*>\s?", re.MULTILINE)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[\s\n]+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")

_VOWEL_GROUP = re.compile(r"[aeiouy]+")


def strip_markdown(text: str) -> str:
    """Reduce markdown to the prose a human actually reads aloud."""
    out = _CODE_BLOCK.sub(" ", text)
    out = _INLINE_CODE.sub(" ", out)
    out = _MD_TABLE.sub(" ", out)
    out = _MD_HEADING.sub(" ", out)
    out = _MD_QUOTE.sub("", out)
    out = _MD_LINK.sub(r"\1", out)
    out = _MD_EMPHASIS.sub(r"\1", out)
    out = _MD_BULLET.sub("", out)
    return re.sub(r"\s+", " ", out).strip()


def count_syllables(word: str) -> int:
    """Heuristic English syllable count.

    Standard vowel-group approach with the usual silent-'e' correction. It is
    approximate, but it is *consistently* approximate, which is all a threshold
    needs.
    """
    w = word.lower().strip("'-")
    if not w:
        return 0
    groups = _VOWEL_GROUP.findall(w)
    count = len(groups)
    # Silent terminal 'e' ("make" -> 1, not 2), but never reduce below 1.
    # Words ending in consonant + "le" ("table", "simple") keep that final
    # syllable, and the vowel-group pass has already counted its 'e' — adding a
    # bonus for it here would double-count, so the exclusion is all that is
    # needed.
    if w.endswith("e") and not w.endswith(("le", "ee", "ye")) and count > 1:
        count -= 1
    return max(1, count)


def split_sentences(prose: str) -> list[str]:
    parts = [s.strip() for s in _SENTENCE_SPLIT.split(prose) if s.strip()]
    return [p for p in parts if _WORD.search(p)]


def words_of(text: str) -> list[str]:
    return _WORD.findall(text)


@dataclass(frozen=True)
class TextStats:
    word_count: int
    sentence_count: int
    syllable_count: int
    avg_sentence_words: float
    long_sentences: list[str]
    long_sentence_ratio: float
    flesch_kincaid_grade: float


def analyse(lesson_markdown: str, long_sentence_words: int = 28) -> TextStats:
    prose = strip_markdown(lesson_markdown)
    sentences = split_sentences(prose)
    words = words_of(prose)

    word_count = len(words)
    sentence_count = max(1, len(sentences))
    syllables = sum(count_syllables(w) for w in words)

    avg_sentence_words = word_count / sentence_count
    avg_syllables_per_word = syllables / max(1, word_count)

    # Flesch-Kincaid Grade Level.
    fk = 0.39 * avg_sentence_words + 11.8 * avg_syllables_per_word - 15.59

    long_sentences = [s for s in sentences if len(words_of(s)) > long_sentence_words]

    return TextStats(
        word_count=word_count,
        sentence_count=len(sentences),
        syllable_count=syllables,
        avg_sentence_words=round(avg_sentence_words, 2),
        long_sentences=long_sentences,
        long_sentence_ratio=round(len(long_sentences) / sentence_count, 3),
        flesch_kincaid_grade=round(fk, 2),
    )


# --------------------------------------------------------------------- jargon

# Terms a beginner in this audience will not know on sight. Each maps to the
# markers that count as "this has been defined nearby".
JARGON_TERMS: dict[str, tuple[str, ...]] = {
    "embedding": ("list of numbers", "numbers that represent", "meaning as numbers",
                  "numerical", "represents the meaning", "turn text into numbers",
                  "converts text into numbers", "captures the meaning"),
    "vector database": ("stores", "database that", "search", "finds", "holds"),
    "vector": ("list of numbers", "numbers", "numerical"),
    "chunk": ("piece", "pieces", "small part", "section", "split", "smaller"),
    "index": ("stored ahead of time", "prepare", "catalogue", "catalog",
              "organise", "organize", "stored in advance", "built in advance"),
    "token": ("piece of a word", "word piece", "chunk of text", "unit of text"),
    "llm": ("large language model", "language model", "ai model"),
    "large language model": ("model", "ai", "trained on"),
    "semantic": ("meaning", "means", "sense"),
    "top-k": ("closest", "best matches", "most relevant", "number of", "top few"),
    "cosine similarity": ("how close", "closeness", "similarity between", "measure of"),
    "fine-tuning": ("training", "retrain", "further training", "adjusts the model",
                    "changing the model", "updates the model"),
    "corpus": ("collection", "set of documents", "body of text"),
    "latency": ("delay", "time it takes", "speed", "how long"),
    "inference": ("running the model", "when the model answers", "generating"),
    "hallucination": ("makes up", "made up", "invents", "confidently wrong",
                      "fabricat", "wrong answer"),
    "prompt": ("what you send", "instruction", "question you give", "text you give",
               "text you send", "input to the model", "message you send",
               "you send to the model", "what goes into the model"),
    "retrieval": ("search", "finding", "looking up", "look up", "fetch", "finds"),
}

# Definition must appear within this many characters of an early occurrence,
# checked in both directions — a lesson may define a term in the sentence
# before it first uses it.
_DEFINITION_WINDOW = 400

# How many early occurrences to inspect. Checking only the very first produces
# false positives on a "What you will learn" contents list, which *names* terms
# it goes on to define. Naming a topic is announcing it, not using it.
_OCCURRENCES_TO_CHECK = 3


def _definition_patterns(term: str) -> list[re.Pattern[str]]:
    """Structural ways English actually introduces a term.

    A curated synonym list alone is too brittle: it cannot anticipate every
    valid phrasing, and when it misses one the check fails a lesson that is
    genuinely correct. The generator then cannot fix it — it rewrites the
    definition, the regex still misses, and the loop cannot converge. An
    unfixable check is worse than no check.

    Matching on the *form* of a definition ("X is …", "X means …", "X: …")
    rather than guessing its wording removes that failure mode. Depth of the
    definition is left to the judged `jargon_defined_on_first_use` check — this
    one only asks whether a definition is present at all.
    """
    t = re.escape(term)
    return [
        # "an embedding is a list of numbers…" / "a hallucination happens when…"
        #
        # The verb list is deliberately broad. Three separate live runs were
        # rejected on definitions that were completely correct but phrased in a
        # way the previous, narrower list did not anticipate — each time the
        # generator rewrote the definition, the regex missed again, and the loop
        # could not converge. Enumerating phrasings is a losing game; the point
        # is to detect *definitional structure*, and depth is the judged check's
        # job. Substance is still required after the verb, so "Hallucination is
        # bad." does not count.
        re.compile(
            rf"\b{t}s?\b\s+(?:"
            r"is|are|was|were|means?|meaning|refers? to|describes?|denotes?|"
            r"happens? when|occurs? when|arises? when|involves?|stands? for|"
            r"lets? you|allows? you|gives? you|helps? you|tells? you"
            rf")\b(?:\s+\S+){{4,}}"
        ),
        # "**Hallucination**: Hallucination is when an AI…"
        re.compile(rf"\b{t}s?\b\s*[:—–-]\s+(?:\S+\s+){{4,}}"),
        # "…called an embedding" / "we call this a chunk"
        re.compile(rf"\bcall(?:ed|s|ing)?\b(?:\s+\w+){{0,3}}\s+(?:an?\s+|the\s+)?{t}s?\b"),
        # "…a list of numbers (an embedding)"
        re.compile(rf"\(\s*(?:an?\s+|the\s+)?{t}s?\s*\)"),
        # "the term embedding means…" / "known as an embedding"
        re.compile(rf"\b(?:known as|term|word)\b(?:\s+\w+){{0,3}}\s+{t}s?\b"),
    ]


def _flatten_for_jargon(text: str) -> str:
    """Remove emphasis markers so definitions are detectable.

    Writers bold the term they are defining — "A **prompt** is the text you send
    to the model" — which is good practice and exactly what a definition looks
    like. But the asterisks sit between the term and its copula, so a pattern
    looking for `prompt is …` never matches and the check rejects a textbook
    definition. This cost two live runs before it was spotted, both of them
    failing on wording that was completely correct.
    """
    out = re.sub(r"[*_]{1,3}", "", text)
    return re.sub(r"[ \t]+", " ", out)


def find_undefined_jargon(lesson_markdown: str) -> list[tuple[str, str]]:
    """Return (term, excerpt) for each term that is never defined anywhere."""
    flattened = _flatten_for_jargon(lesson_markdown)
    lowered = flattened.lower()
    offenders: list[tuple[str, str]] = []

    defined_terms: set[str] = set()

    for term, markers in JARGON_TERMS.items():
        # `\bembedding\b` does not match "embeddings" — the trailing 's' kills the
        # word boundary — so every plural use was being skipped silently. That is
        # a leniency bug: the check simply stopped looking at half the real uses.
        occurrences = list(re.finditer(rf"\b{re.escape(term)}s?\b", lowered))
        if not occurrences:
            continue

        patterns = _definition_patterns(term)
        defined = False

        for match in occurrences:
            start = max(0, match.start() - _DEFINITION_WINDOW)
            end = min(len(lowered), match.end() + _DEFINITION_WINDOW)
            window = lowered[start:end]

            if any(marker in window for marker in markers) or any(
                p.search(window) for p in patterns
            ):
                defined = True
                break

        if defined:
            defined_terms.add(term)
            continue

        # A term that only ever appears inside a longer term already accounted
        # for is not an independent use. "vector" inside "vector database" was
        # being reported separately even when the compound was clearly defined,
        # producing a failure the writer could only fix by defining a word they
        # never actually used on its own.
        if any(
            term != other and term in other and other in defined_terms
            for other in JARGON_TERMS
        ):
            bare = re.sub(
                r"|".join(
                    rf"\b{re.escape(o)}s?\b" for o in JARGON_TERMS if o != term and term in o
                ),
                " ",
                lowered,
            )
            if not re.search(rf"\b{re.escape(term)}s?\b", bare):
                continue

        first = occurrences[0]
        excerpt_start = max(0, first.start() - 70)
        excerpt = flattened[excerpt_start : first.end() + 70].strip()
        offenders.append((term, excerpt.replace("\n", " ")))

    return offenders


# ------------------------------------------------------------------- markers

_ANALOGY_MARKERS = (
    "think of it like", "imagine", "just like", "similar to", "is like a",
    "picture a", "picture this", "the same way", "analogy", "as if you",
    "compare this to", "it works like",
)
_EXAMPLE_MARKERS = (
    "for example", "for instance", "let's say", "lets say", "suppose",
    "say you", "here is an example", "here's an example", "worked example",
    "step by step", "walk through", "consider this",
)
_THREE_STEPS = ("retriev", "augment", "generat")


def count_markers(lesson_markdown: str, markers: tuple[str, ...]) -> int:
    lowered = lesson_markdown.lower()
    return sum(lowered.count(m) for m in markers)


def missing_pipeline_words(lesson_markdown: str) -> list[str]:
    lowered = lesson_markdown.lower()
    labels = {"retriev": "retrieve", "augment": "augment", "generat": "generate"}
    return [labels[stem] for stem in _THREE_STEPS if stem not in lowered]


# ------------------------------------------------------------- check runners


def run_deterministic_checks(
    lesson_markdown: str, thresholds: ReadabilityThresholds
) -> list[CheckResult]:
    """Execute every deterministic checkpoint and return its verdict."""
    stats = analyse(lesson_markdown, thresholds.long_sentence_words)
    results: list[CheckResult] = []

    def add(check_id: str, passed: bool, reason: str, evidence: str, blocking: bool = True):
        results.append(
            CheckResult(
                check_id=check_id,
                passed=passed,
                reason="" if passed else reason,
                evidence=evidence,
                kind=CheckKind.DETERMINISTIC,
                blocking=blocking,
            )
        )

    # --- readability_grade
    fk_ok = stats.flesch_kincaid_grade <= thresholds.max_flesch_kincaid_grade
    add(
        "readability_grade",
        fk_ok,
        (
            f"Flesch-Kincaid grade level is {stats.flesch_kincaid_grade}, above the "
            f"limit of {thresholds.max_flesch_kincaid_grade}. The writing is too "
            f"advanced for a beginner reading in a second language."
        ),
        f"grade={stats.flesch_kincaid_grade} avg_sentence_words={stats.avg_sentence_words}",
    )

    # --- sentence_length
    avg_ok = stats.avg_sentence_words <= thresholds.max_avg_sentence_words
    ratio_ok = stats.long_sentence_ratio <= thresholds.max_long_sentence_ratio
    worst = max(stats.long_sentences, key=len, default="")
    add(
        "sentence_length",
        avg_ok and ratio_ok,
        (
            f"Average sentence is {stats.avg_sentence_words} words "
            f"(limit {thresholds.max_avg_sentence_words}); "
            f"{stats.long_sentence_ratio:.0%} of sentences exceed "
            f"{thresholds.long_sentence_words} words "
            f"(limit {thresholds.max_long_sentence_ratio:.0%})."
        ),
        worst[:300],
    )

    # --- no_runaway_sentence
    # Absolute ceiling, deliberately independent of the averages above.
    prose_sentences = split_sentences(strip_markdown(lesson_markdown))
    runaway = [
        s for s in prose_sentences
        if len(words_of(s)) > thresholds.absolute_max_sentence_words
    ]
    worst_runaway = max(runaway, key=lambda s: len(words_of(s)), default="")
    add(
        "no_runaway_sentence",
        not runaway,
        (
            f"{len(runaway)} sentence(s) exceed the absolute limit of "
            f"{thresholds.absolute_max_sentence_words} words. The longest is "
            f"{len(words_of(worst_runaway))} words. A reader in their second "
            f"language cannot hold a sentence this long."
        ),
        worst_runaway[:400],
    )

    # --- jargon_density
    undefined = find_undefined_jargon(lesson_markdown)
    add(
        "jargon_density",
        len(undefined) <= thresholds.max_undefined_jargon,
        (
            "These technical terms are used without a plain-English definition "
            "nearby: " + ", ".join(t for t, _ in undefined) + "."
        ),
        " || ".join(f"{t}: …{ex}…" for t, ex in undefined[:4]),
    )

    # --- example_density
    analogies = count_markers(lesson_markdown, _ANALOGY_MARKERS)
    examples = count_markers(lesson_markdown, _EXAMPLE_MARKERS)
    add(
        "example_density",
        analogies >= thresholds.min_analogy_markers
        and examples >= thresholds.min_worked_example_markers,
        (
            f"Found {analogies} analogy signpost(s) and {examples} example "
            f"signpost(s); need at least {thresholds.min_analogy_markers} and "
            f"{thresholds.min_worked_example_markers}."
        ),
        f"analogy_markers={analogies} example_markers={examples}",
    )

    # --- covers_three_steps
    missing = missing_pipeline_words(lesson_markdown)
    add(
        "covers_three_steps",
        not missing,
        f"The lesson never uses these pipeline words: {', '.join(missing)}.",
        f"missing={missing}",
    )

    # --- length_in_range (advisory)
    length_ok = thresholds.min_words <= stats.word_count <= thresholds.max_words
    add(
        "length_in_range",
        length_ok,
        (
            f"Word count is {stats.word_count}; target range is "
            f"{thresholds.min_words}-{thresholds.max_words}."
        ),
        f"word_count={stats.word_count}",
        blocking=False,
    )

    return results
