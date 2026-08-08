"""Shared data shapes for the diff engine (plain dataclasses, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.policy_engine.changes import MaterialityLevel


@dataclass(frozen=True)
class SectionUnit:
    """A top-level numbered section of a regulation — the unit the engine diffs.

    ``title`` comes from the authoritative Table of Contents; ``body`` (when available) is the
    section's text in the document body, used for CREATED text and citation spans.
    """

    number: int
    title: str
    char_start: int | None = None
    char_end: int | None = None
    body: str = ""

    @property
    def has_body(self) -> bool:
        return bool(self.body)


@dataclass(frozen=True)
class MatchPair:
    """One entry of the optimal assignment between old and new units."""

    old_index: int | None   # index into old units, or None (a CREATED)
    new_index: int | None   # index into new units, or None (a REMOVED)
    similarity: float          # 1 - cost; 0.0 for a null-option (unmatched) side
    relation: str              # MATCHED | RENUMBERED | ADDED | DELETED


@dataclass
class ChangeRow:
    """One row of the change-list — mirrors the persisted ``RegulatoryChange``."""

    change_type: str                       # created | modified | removed
    obligation: str                        # human-readable label (the section title)
    changed_fields: list[str] = field(default_factory=list)
    old_ref: str | None = None          # e.g. "§31"
    new_ref: str | None = None
    old_text: str | None = None
    new_text: str | None = None
    materiality: MaterialityLevel = MaterialityLevel.NONE
    materiality_reasons: list[dict] = field(default_factory=list)
    similarity_score: float | None = None
    confidence: float = 1.0
    requires_confirmation: bool = False
    description: str = ""
    citations: dict = field(default_factory=dict)  # {"old": {...}, "new": {...}}


@dataclass
class TextDiffResult:
    """Level-1 output: how much of the document is byte-identical (the pre-filter win)."""

    identical_ratio: float
    changed_old_blocks: int
    changed_new_blocks: int
    total_old_blocks: int
    total_new_blocks: int


@dataclass
class DiffResult:
    """The full engine output."""

    changes: list[ChangeRow]
    summary: dict                 # {created, modified, removed, material, cosmetic_suppressed}
    text_diff: TextDiffResult
    old_section_count: int
    new_section_count: int
    matcher: dict                 # {algorithm, tau, similarity_backend}
    notes: list[str] = field(default_factory=list)
