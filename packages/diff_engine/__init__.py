"""The 4-level regulatory diff engine.

Turns two versions of a regulation into a structured, cited, materiality-scored change-list.
The LLM never arbitrates: embeddings/lexical similarity *gate the matching*, and the pure
Policy Decision Engine (``packages.policy_engine``) *gates the verdict*.

Levels (coarse → fine):
  L1 ``text_diff``       — normalized paragraph anchor diff; short-circuits identical regions.
  L2 ``structural_diff`` — align section trees by number + title similarity.
  L3 ``semantic_diff``   — Hungarian optimal assignment over leftover units (beats greedy).
  L4 ``obligation_diff`` — field-level compare via ``classify_change`` → CREATED/MODIFIED/REMOVED.

``engine.run_diff_pipeline`` composes them into a ``DiffResult`` with no DB/LLM dependency.
"""

from packages.diff_engine.engine import run_diff_pipeline
from packages.diff_engine.types import ChangeRow, DiffResult, SectionUnit

__all__ = ["run_diff_pipeline", "DiffResult", "ChangeRow", "SectionUnit"]
