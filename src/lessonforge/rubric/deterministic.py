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

# Definition must appear within this many characters of first use (either side).
_DEFINITION_WINDOW = 320


def find_undefined_jargon(lesson_markdown: str) -> list[tuple[str, str]]:
    """Return (term, first-use excerpt) for each term used without a nearby definition.

    "Nearby" is a character window around the first occurrence, checked in both
    directions — a lesson may define the term in the sentence before it uses it.
    """
    lowered = lesson_markdown.lower()
    offenders: list[tuple[str, str]] = []

    for term, markers in JARGON_TERMS.items():
        match = re.search(rf"\b{re.escape(term)}\b", lowered)
        if not match:
            continue

        start = max(0, match.start() - _DEFINITION_WINDOW)
        end = min(len(lowered), match.end() + _DEFINITION_WINDOW)
        window = lowered[start:end]

        if any(marker in window for marker in markers):
            continue

        excerpt_start = max(0, match.start() - 70)
        excerpt = lesson_markdown[excerpt_start : match.end() + 70].strip()
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
