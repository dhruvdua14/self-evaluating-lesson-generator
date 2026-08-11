"""lessonforge — a self-evaluating lesson content generator.

Generates a beginner lesson, judges it against a hard pass/fail rubric, and
regenerates from the failure reasons until it clears the bar or the retry budget
runs out. Learns from repeated failures across runs.
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
