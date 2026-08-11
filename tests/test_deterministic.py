"""Deterministic checks must be exactly that: deterministic and correct."""

from __future__ import annotations

from lessonforge.config import ReadabilityThresholds
from lessonforge.rubric.deterministic import (
    analyse,
    count_syllables,
    find_undefined_jargon,
    missing_pipeline_words,
    run_deterministic_checks,
    split_sentences,
    strip_markdown,
)

TH = ReadabilityThresholds()


def _results(text: str) -> dict[str, bool]:
    return {r.check_id: r.passed for r in run_deterministic_checks(text, TH)}


# ------------------------------------------------------------------ primitives


def test_syllable_counting_handles_silent_e_and_le():
    assert count_syllables("make") == 1
    assert count_syllables("cat") == 1
    assert count_syllables("table") == 2
    assert count_syllables("retrieval") == 3
    assert count_syllables("a") == 1


def test_strip_markdown_removes_scaffolding_but_keeps_prose():
    md = "# Heading\n\nSome **bold** text.\n\n```\ncode here\n```\n\n- bullet one\n"
    out = strip_markdown(md)
    assert "code here" not in out
    assert "Heading" not in out
    assert "bold" in out
    assert "bullet one" in out


def test_sentence_splitting_ignores_empty_fragments():
    assert len(split_sentences("One. Two! Three?  ")) == 3


# ------------------------------------------------------------- discrimination


def test_good_lesson_passes_every_deterministic_check(good_lesson):
    failures = [
        r.check_id for r in run_deterministic_checks(good_lesson, TH) if not r.passed
    ]
    assert failures == [], f"golden lesson should pass everything, failed: {failures}"


def test_bad_lesson_fails_the_language_checks(bad_lesson):
    results = _results(bad_lesson)
    assert results["readability_grade"] is False
    assert results["sentence_length"] is False
    assert results["jargon_density"] is False
    assert results["example_density"] is False


def test_checks_are_deterministic(good_lesson):
    """Same input, same verdict — the whole point of not using an LLM here."""
    first = [(r.check_id, r.passed, r.reason) for r in run_deterministic_checks(good_lesson, TH)]
    for _ in range(3):
        again = [(r.check_id, r.passed, r.reason) for r in run_deterministic_checks(good_lesson, TH)]
        assert again == first


# ------------------------------------------------------------------- jargon


def test_undefined_jargon_is_flagged():
    text = "We use an embedding to search. The vector database is fast."
    flagged = {term for term, _ in find_undefined_jargon(text)}
    assert "embedding" in flagged


def test_defined_jargon_is_not_flagged():
    text = (
        "An embedding is a list of numbers that represents the meaning of text. "
        "We create an embedding for every piece of the document."
    )
    flagged = {term for term, _ in find_undefined_jargon(text)}
    assert "embedding" not in flagged


def test_structural_definitions_are_recognised():
    """Regression: a curated synonym list alone produced unfixable false positives.

    A live run failed three times on `jargon_density` while the lesson was
    defining its terms perfectly well — the phrasing simply was not in the
    synonym list. The generator rewrote the definition each time and the regex
    kept missing it, so the loop could not converge. Matching the *form* of a
    definition fixes that; each phrasing below is one the live model actually
    produced or a close variant.
    """
    for text in (
        "Hallucination: Hallucination is when an AI creates a confident answer that is false.",
        "An embedding is a set of numbers capturing what the sentence is about.",
        "We split the document into small pieces, and each piece is called a chunk.",
        "The model turns your words into numbers (an embedding) before searching.",
        "This is known as fine-tuning, which further trains the model on new data.",
    ):
        flagged = {term for term, _ in find_undefined_jargon(text)}
        assert not flagged, f"false positive on: {text!r} -> {flagged}"


def test_thin_definitions_are_still_rejected():
    """The structural match must require substance, not just a copula."""
    assert {t for t, _ in find_undefined_jargon("Hallucination is bad.")} == {"hallucination"}


def test_term_named_in_a_contents_list_then_defined_later_passes():
    """A 'what you will learn' list names topics; naming is not using."""
    text = (
        "## What you will learn\n"
        "- How RAG differs from fine-tuning a model.\n\n"
        "## Later\n"
        "Fine-tuning means further training the model on your own examples so it "
        "changes its own behaviour permanently.\n"
    )
    assert "fine-tuning" not in {t for t, _ in find_undefined_jargon(text)}


def test_jargon_definition_window_looks_backwards_too():
    """A term defined in the preceding sentence counts as defined."""
    text = (
        "Each small piece of a document is stored separately. "
        "We call each piece a chunk."
    )
    flagged = {term for term, _ in find_undefined_jargon(text)}
    assert "chunk" not in flagged


# --------------------------------------------------------------- runaway gate


def test_runaway_sentence_caught_even_when_averages_are_fine():
    """The gap that document-level averaging cannot close.

    Many short sentences plus one enormous one keeps every average inside its
    limit. `no_runaway_sentence` exists for exactly this case.
    """
    short = "This is short. " * 120
    runaway = " ".join(["word"] * 80) + "."
    text = short + runaway

    stats = analyse(text, TH.long_sentence_words)
    assert stats.flesch_kincaid_grade <= TH.max_flesch_kincaid_grade
    assert stats.avg_sentence_words <= TH.max_avg_sentence_words

    assert _results(text)["no_runaway_sentence"] is False


def test_no_runaway_sentence_passes_on_clean_text(good_lesson):
    assert _results(good_lesson)["no_runaway_sentence"] is True


# ------------------------------------------------------------------ coverage


def test_missing_pipeline_words_detected():
    assert set(missing_pipeline_words("this mentions nothing useful")) == {
        "retrieve", "augment", "generate",
    }
    assert missing_pipeline_words("retrieve, augment, then generate") == []


def test_advisory_check_does_not_block():
    """length_in_range must be advisory, never blocking."""
    short = "Retrieve augment generate. For example, think of it like a book."
    blocking_failures = [
        r for r in run_deterministic_checks(short, TH) if r.blocking and not r.passed
    ]
    assert all(r.check_id != "length_in_range" for r in blocking_failures)


def test_bold_markers_do_not_hide_a_definition():
    """Regression: markdown emphasis broke definition detection.

    Writers bold the term they are defining — which is good practice and
    exactly what a definition looks like — but the asterisks sit between the
    term and its verb, so `prompt is ...` never matched. Two live runs were
    rejected on wording that was completely correct.
    """
    text = "A **prompt** is the text input or question you write to the model."
    assert "prompt" not in {t for t, _ in find_undefined_jargon(text)}


def test_definition_verbs_beyond_the_copula_are_recognised():
    """Enumerating phrasings is a losing game; detect definitional structure."""
    for text in (
        "A hallucination happens when a model gives a confident answer that is wrong.",
        "Chunking means breaking a long document into smaller readable pieces.",
        "An embedding refers to a list of numbers standing for the meaning of text.",
        "Indexing describes the work of preparing documents before any question arrives.",
    ):
        flagged = {t for t, _ in find_undefined_jargon(text)}
        term = text.split()[1].lower().rstrip(",.")
        assert term not in flagged, f"false positive on {text!r}"


def test_plural_uses_are_not_skipped():
    """`\\bembedding\\b` never matched "embeddings" — half of real uses were missed."""
    assert "embedding" in {t for t, _ in find_undefined_jargon("Embeddings are useful.")}


def test_subterm_is_not_flagged_when_only_the_compound_is_used():
    """"vector" inside "vector database" is not an independent use.

    Reporting it separately produced a failure the writer could only fix by
    defining a word they never used on its own.
    """
    text = "A vector database is a store that finds the closest matching pieces quickly."
    assert "vector" not in {t for t, _ in find_undefined_jargon(text)}


def test_subterm_is_still_flagged_when_used_alone():
    text = "A vector database is a store that finds the closest matches. Each vector is opaque."
    assert "vector" in {t for t, _ in find_undefined_jargon(text)}
