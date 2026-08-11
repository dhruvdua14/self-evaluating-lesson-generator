"""Structured contracts exchanged between nodes.

Every LLM call in this system except the lesson-writing call itself returns a
schema-validated object. Prose is only allowed where prose is the product.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LessonPlan(BaseModel):
    """Output of the Planner node.

    The planner decides *what to teach*; the generator decides *how to say it*.
    Splitting them means a retry triggered by a language failure does not force
    the curriculum to be re-derived, and a retry triggered by a coverage failure
    can target the plan directly.
    """

    topic: str
    one_sentence_definition: str = Field(
        description="What the topic is, in one sentence a 12th-grade graduate understands."
    )
    learning_objectives: list[str] = Field(
        description="3-6 concrete things the reader can do or explain afterwards."
    )
    prerequisite_concepts: list[str] = Field(
        default_factory=list,
        description="Concepts that must be explained inside the lesson because the reader will not have them.",
    )
    concept_order: list[str] = Field(
        description="Concepts in strict teaching order. Nothing may appear before what it depends on."
    )
    analogy: str = Field(
        description="One everyday analogy, understandable in India without Western cultural knowledge."
    )
    worked_example: str = Field(
        description="One specific question to trace end to end through the whole pipeline."
    )
    common_misconceptions: list[str] = Field(
        default_factory=list,
        description="Beginner misconceptions the lesson must explicitly correct.",
    )
    jargon_to_define: list[str] = Field(
        default_factory=list,
        description="Technical terms that will appear and therefore must be defined on first use.",
    )


class PatchProposal(BaseModel):
    """A single learned directive proposed by the Reflector."""

    check_id: str
    directive: str = Field(
        description="One imperative sentence to add to the generator's system prompt."
    )
    rationale: str = Field(description="Why this directive prevents the observed failure.")


class ReflectionOutput(BaseModel):
    """Output of the Reflector node — the self-evolving step."""

    patches: list[PatchProposal] = Field(default_factory=list)
