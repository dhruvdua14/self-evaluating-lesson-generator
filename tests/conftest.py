from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from lessonforge.config import Settings
from lessonforge.llm.mock import MockProvider
from lessonforge.memory import MemoryStore

FIXTURES = Path(__file__).resolve().parents[1] / "src" / "lessonforge" / "llm" / "fixtures"


@pytest.fixture
def good_lesson() -> str:
    return (FIXTURES / "draft_good.md").read_text(encoding="utf-8")


@pytest.fixture
def bad_lesson() -> str:
    return (FIXTURES / "draft_bad.md").read_text(encoding="utf-8")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Isolated settings: temp DB, temp output, mock provider."""
    return replace(
        Settings(),
        provider="mock",
        api_key=None,
        memory_db=tmp_path / "memory.db",
        output_dir=tmp_path / "output",
    )


@pytest.fixture
def store(settings: Settings) -> MemoryStore:
    return MemoryStore(settings.memory_db)


@pytest.fixture
def provider() -> MockProvider:
    return MockProvider()
