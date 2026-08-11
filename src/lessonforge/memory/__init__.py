"""Persistent memory and the self-evolving layer."""

from .evolve import EvolutionReport, build_patch_block, reflect_and_evolve
from .store import FailurePattern, MemoryStore, Patch

__all__ = [
    "EvolutionReport",
    "FailurePattern",
    "MemoryStore",
    "Patch",
    "build_patch_block",
    "reflect_and_evolve",
]
