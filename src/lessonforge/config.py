"""Central configuration.

Every tunable lives here so the loop's behaviour can be audited from one file
instead of being scattered across prompts and nodes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
KNOWLEDGE_DIR = PACKAGE_ROOT / "knowledge"
PROMPTS_DIR = PACKAGE_ROOT / "prompts"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class ReadabilityThresholds:
    """Deterministic language gates.

    Calibrated for the target learner: a 12th-grade graduate from India with
    limited English vocabulary from a non-English-medium background. These are
    intentionally strict — an average sentence of 20+ words is a wall of text
    for someone reading in their second or third language.
    """

    max_flesch_kincaid_grade: float = 9.0
    max_avg_sentence_words: float = 20.0
    max_long_sentence_ratio: float = 0.15  # share of sentences over 28 words
    long_sentence_words: int = 28
    # Absolute per-sentence ceiling. The three thresholds above are document
    # averages and are therefore robust to one terrible paragraph — good for
    # measuring overall register, useless for catching localised damage. A
    # beginner only has to hit one impenetrable sentence to give up, so this is
    # a hard floor no averaging can smooth over.
    absolute_max_sentence_words: int = 45
    max_undefined_jargon: int = 0
    min_words: int = 700
    max_words: int = 2200
    min_analogy_markers: int = 1
    min_worked_example_markers: int = 1


@dataclass(frozen=True)
class LoopPolicy:
    """Termination guarantees for the agentic loop.

    `max_retries` is the number of *regenerations* after the first attempt, so
    total attempts == max_retries + 1. The assessment asks for 1-2 retries; we
    default to 2 and hard-cap at 3 so the loop can never spin.
    """

    max_retries: int = 2
    hard_cap_attempts: int = 4
    stop_on_first_pass: bool = True


@dataclass(frozen=True)
class EvolutionPolicy:
    """Controls the self-evolving layer.

    A directive is only synthesised once a check has failed `patch_threshold`
    times across the lifetime of the memory store. This avoids over-fitting the
    generator prompt to a single unlucky run.
    """

    enabled: bool = True
    patch_threshold: int = 2
    max_active_patches: int = 8
    # A blocking check that has never failed across this many runs is reported
    # as non-discriminating for human review. We never auto-delete a check.
    non_discriminating_after_runs: int = 8


@dataclass(frozen=True)
class Settings:
    provider: str = field(default_factory=lambda: os.getenv("LF_PROVIDER", "gemini"))
    api_key: str | None = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    )

    # Two different models by design: the generator is the strong writer, the
    # judge is a separate, cheaper call. See ARCHITECTURE.md "Judge independence".
    generator_model: str = field(
        default_factory=lambda: os.getenv("LF_GENERATOR_MODEL", "gemini-2.5-pro")
    )
    planner_model: str = field(
        default_factory=lambda: os.getenv("LF_PLANNER_MODEL", "gemini-2.5-flash")
    )
    judge_model: str = field(
        default_factory=lambda: os.getenv("LF_JUDGE_MODEL", "gemini-2.5-pro")
    )
    reflector_model: str = field(
        default_factory=lambda: os.getenv("LF_REFLECTOR_MODEL", "gemini-2.5-flash")
    )

    generator_temperature: float = field(
        default_factory=lambda: _env_float("LF_GENERATOR_TEMPERATURE", 0.7)
    )
    # The judge runs near-deterministic on purpose: a rubric that returns a
    # different verdict on identical input is not a rubric.
    judge_temperature: float = field(
        default_factory=lambda: _env_float("LF_JUDGE_TEMPERATURE", 0.0)
    )
    max_output_tokens: int = field(
        default_factory=lambda: _env_int("LF_MAX_OUTPUT_TOKENS", 16000)
    )

    memory_db: Path = field(
        default_factory=lambda: Path(
            os.getenv("LF_MEMORY_DB", str(PROJECT_ROOT / "memory" / "lessonforge.db"))
        )
    )
    output_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("LF_OUTPUT_DIR", str(PROJECT_ROOT / "output"))
        )
    )

    readability: ReadabilityThresholds = field(default_factory=ReadabilityThresholds)
    loop: LoopPolicy = field(default_factory=LoopPolicy)
    evolution: EvolutionPolicy = field(default_factory=EvolutionPolicy)

    def ground_truth(self) -> str:
        return (KNOWLEDGE_DIR / "rag_ground_truth.md").read_text(encoding="utf-8")

    def prompt(self, name: str) -> str:
        return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def load_settings(**overrides: object) -> Settings:
    """Build settings, applying explicit overrides from the CLI last."""
    settings = Settings()
    if not overrides:
        return settings
    clean = {k: v for k, v in overrides.items() if v is not None}
    if not clean:
        return settings
    from dataclasses import replace

    return replace(settings, **clean)  # type: ignore[arg-type]
