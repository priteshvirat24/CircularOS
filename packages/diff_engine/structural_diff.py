"""Level 2 — structural alignment of section trees by title (+ number).

Aligns two section lists by exact normalized-title equality first (the strong, unambiguous
signal that survives a re-consolidation's renumbering), pairing each match to the new section
with the nearest number when a title repeats. Whatever is left unmatched is handed to Level 3
(semantic assignment) — a clause may have been reworded *and* renumbered at once.

Relations: ``MATCHED`` (same number, same title) and ``RENUMBERED`` (different number, same
title) are cosmetic; the engine will not report them as substantive changes.
"""

from __future__ import annotations

from packages.diff_engine.normalize import normalize_for_match
from packages.diff_engine.types import SectionUnit


class StructuralAlignment:
    def __init__(self) -> None:
        self.matched: list[tuple[int, int, str]] = []  # (old_idx, new_idx, relation)
        self.leftover_old: list[int] = []
        self.leftover_new: list[int] = []


def align_sections(old: list[SectionUnit], new: list[SectionUnit]) -> StructuralAlignment:
    result = StructuralAlignment()

    new_by_title: dict[str, list[int]] = {}
    for j, s in enumerate(new):
        new_by_title.setdefault(normalize_for_match(s.title), []).append(j)

    used_new: set[int] = set()
    for i, s in enumerate(old):
        key = normalize_for_match(s.title)
        candidates = [j for j in new_by_title.get(key, []) if j not in used_new]
        if not candidates:
            result.leftover_old.append(i)
            continue
        # Prefer the new section with the nearest number (renumber shift is small).
        j = min(candidates, key=lambda jj: abs(new[jj].number - s.number))
        used_new.add(j)
        relation = "MATCHED" if new[j].number == s.number else "RENUMBERED"
        result.matched.append((i, j, relation))

    result.leftover_new = [j for j in range(len(new)) if j not in used_new]
    return result
