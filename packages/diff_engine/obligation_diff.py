"""Level 4 — obligation-level diff over the optimal matching.

For each aligned section pair, build comparable ``ObligationFields`` and run the pure
``classify_change`` → CREATED / MODIFIED / REMOVED as set operations over the matching (§3),
with ``changed_fields = Δ(o, n)``. Materiality is the deterministic ``assess_materiality``.

For this Aug→Jun re-consolidation the comparable structured field is the authoritative section
title (Jun-2025 obligations were not extracted in Phase 1); richer field-level deltas
(deadline/actor/evidence) flow through the *same* pure functions once both sides are extracted
in Phase 3. The engine never lets an LLM decide a verdict here.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from packages.diff_engine.matching import hungarian_matching
from packages.diff_engine.normalize import canonical_title, clean_document_text
from packages.diff_engine.semantic_diff import build_cost_matrix, lexical_similarity
from packages.diff_engine.types import ChangeRow, SectionUnit
from packages.policy_engine.changes import (
    ChangeKind,
    MaterialityLevel,
    MaterialityVerdict,
    ObligationFields,
    assess_materiality,
    classify_change,
)

# Similarity floor for matching two obligations *within* an already-aligned section pair. Set
# high on purpose: only near-identical obligations are field-compared, so under a bounded or
# asymmetric extraction two *different* obligations can't align and manufacture a spurious field
# delta. Genuinely reworded obligations that fall below this go to the null option (counted, not
# flipped) — the conservative choice for a regulator (never invent a change).
_OBLIGATION_TAU = 0.72

# A section pair's obligation field-deltas are trusted only when at least this fraction of the
# larger side's obligations found a match — i.e. the two sides were extracted comparably.
_COVERAGE_FLOOR = 0.8

_LEVEL_ORDER = {
    MaterialityLevel.NONE: 0, MaterialityLevel.LOW: 1,
    MaterialityLevel.MEDIUM: 2, MaterialityLevel.HIGH: 3,
}


@dataclass
class ObligationCompare:
    """Result of the obligation-level field diff within one aligned section pair."""

    n_old: int
    n_new: int
    n_matched: int
    field_deltas: list[str] = field(default_factory=list)  # union of changed fields, matched pairs
    created: int = 0   # informational count only (see note) — never flips a section by itself
    removed: int = 0   # informational count only
    max_materiality: MaterialityLevel = MaterialityLevel.NONE
    reasons: list[dict] = field(default_factory=list)

    @property
    def coverage_ratio(self) -> float:
        """Fraction of the larger side's obligations that matched a partner — a proxy for
        whether the two sides were extracted comparably. Low ⇒ asymmetric coverage."""
        denom = max(self.n_old, self.n_new)
        return (self.n_matched / denom) if denom else 0.0

    @property
    def has_field_delta(self) -> bool:
        """A *trustworthy* obligation field change: matched-pair deltas exist AND the two sides'
        obligations actually correspond (high coverage).

        Two guards against manufacturing changes from incomplete data:
        1. Created/removed *counts* are excluded — under a bounded/asymmetric extraction they are
           coverage artifacts, not real creation/removal, and must never flip a renumbered section.
        2. Field deltas are trusted only when ``coverage_ratio`` is high. When one side was
           extracted far more sparsely than the other (e.g. 8 of 39 matched), the "matched" pairs
           are similarity-forced alignments of *different* obligations, so their deltas are noise.
        """
        return bool(self.field_deltas) and self.coverage_ratio >= _COVERAGE_FLOOR


def _obl_text(o: ObligationFields) -> str:
    return f"{o.normalized_obligation or ''} {o.action or ''} {o.object or ''}".strip()


def compare_obligations(
    old_obls: Sequence[ObligationFields],
    new_obls: Sequence[ObligationFields],
    tau: float = _OBLIGATION_TAU,
) -> ObligationCompare:
    """Field-level diff of the structured obligations inside one aligned section pair.

    Obligations are matched old↔new by the optimal (Hungarian) assignment on normalized-text
    similarity; each matched pair is classified with the pure ``classify_change`` and scored with
    ``assess_materiality``; unmatched obligations become created/removed. Pure — no I/O.
    """
    old_obls = list(old_obls)
    new_obls = list(new_obls)
    result = ObligationCompare(n_old=len(old_obls), n_new=len(new_obls), n_matched=0)
    if not old_obls and not new_obls:
        return result

    deltas: set[str] = set()

    def _bump(m: MaterialityVerdict) -> None:
        if _LEVEL_ORDER[m.level] > _LEVEL_ORDER[result.max_materiality]:
            result.max_materiality = m.level
        result.reasons.extend(m.reasons)

    if old_obls and new_obls:
        cost = build_cost_matrix([_obl_text(o) for o in old_obls],
                                 [_obl_text(o) for o in new_obls], lexical_similarity)
        assign = hungarian_matching(cost, tau)
        result.n_matched = len(assign.pairs)
        for i, j, _sim in assign.pairs:
            verdict = classify_change(old_obls[i], new_obls[j])
            if verdict.is_substantive:
                deltas.update(verdict.changed_fields)
                _bump(assess_materiality(verdict, old_obls[i], new_obls[j]))
        # Unmatched obligations are counted but do NOT contribute materiality/reasons: under a
        # bounded extraction they reflect coverage, not real creation/removal.
        result.created = len(assign.unmatched_new)
        result.removed = len(assign.unmatched_old)
    elif new_obls:
        result.created = len(new_obls)
    else:
        result.removed = len(old_obls)

    result.field_deltas = sorted(deltas)
    return result

# Keywords that mark a newly-created obligation as high-risk for the CREATED-materiality rule.
_HIGH_RISK = re.compile(
    r"\b(monitor|supervis|surveillance|audit|fraud|misappropriat|divers|"
    r"cyber|security|default|penalt|misuse|unauthoris|unauthorized|risk reduction)\w*",
    re.IGNORECASE,
)


def _risk_level(text: str) -> str:
    return "high" if _HIGH_RISK.search(text or "") else "medium"


def _fields_from_section(sec: SectionUnit, with_risk: bool = False) -> ObligationFields:
    canon = canonical_title(sec.title)
    return ObligationFields(
        normalized_obligation=canon,
        object=canon,
        # Risk keys on the section *title* (its subject), not the body — every regulatory body
        # mentions penalties/defaults, so body-keying would fire HIGH almost everywhere.
        risk_level=_risk_level(sec.title) if with_risk else None,
    )


def _ref(sec: SectionUnit) -> str:
    return f"§{sec.number}"


def _body_excerpt(sec: SectionUnit, limit: int = 1200) -> str:
    body = clean_document_text(sec.body) or sec.title
    return re.sub(r"[ \t]+", " ", body)[:limit].strip()


def _to_row(kind: ChangeKind, changed_fields: Sequence[str],
            materiality: MaterialityVerdict, old: SectionUnit | None,
            new: SectionUnit | None, similarity: float | None) -> ChangeRow:
    citations: dict = {}
    if old is not None and old.char_start is not None:
        citations["old"] = {"ref": _ref(old), "span": [old.char_start, old.char_end]}
    if new is not None and new.char_start is not None:
        citations["new"] = {"ref": _ref(new), "span": [new.char_start, new.char_end]}

    label = (new or old).title  # type: ignore[union-attr]
    return ChangeRow(
        change_type=kind.value,
        obligation=label,
        changed_fields=list(changed_fields),
        old_ref=_ref(old) if old else None,
        new_ref=_ref(new) if new else None,
        old_text=(_body_excerpt(old) if old else None),
        new_text=(_body_excerpt(new) if new else None),
        materiality=materiality.level,
        materiality_reasons=list(materiality.reasons),
        similarity_score=(round(similarity, 4) if similarity is not None else None),
        requires_confirmation=materiality.requires_confirmation,
        description=materiality.explanation,
        citations=citations,
    )


def diff_pair(
    old: SectionUnit,
    new: SectionUnit,
    similarity: float,
    old_obls: Sequence[ObligationFields] | None = None,
    new_obls: Sequence[ObligationFields] | None = None,
) -> ChangeRow | None:
    """Compare a matched section pair. Returns a MODIFIED row, or None if not substantive.

    The section-title comparison is authoritative for *existence* of the change. When extracted
    obligations are supplied for both sides, an obligation-level field diff runs too: real field
    deltas (deadline/actor/evidence/…) fold into ``changed_fields`` and lift materiality, and an
    obligation-compare summary is attached — so on a substantive amendment L4 reports the actual
    field changes, while on a re-consolidation it corroborates "no change to the underlying duty".
    """
    of_old, of_new = _fields_from_section(old), _fields_from_section(new)
    section_verdict = classify_change(of_old, of_new)
    section_mat = (
        assess_materiality(section_verdict, of_old, of_new)
        if section_verdict.is_substantive else None
    )

    obl = compare_obligations(old_obls or [], new_obls or []) if (old_obls or new_obls) else None
    # Only a matched-pair field delta may flip/elevate a section — never a bare count difference.
    obl_flips = obl is not None and obl.has_field_delta

    if not section_verdict.is_substantive and not obl_flips:
        return None  # cosmetic / renumber-only, and no obligation field change → not reported

    changed: set[str] = set(section_verdict.changed_fields)
    reasons: list[dict] = list(section_mat.reasons) if section_mat else []
    level = section_mat.level if section_mat else MaterialityLevel.NONE

    if obl is not None and obl.has_field_delta:
        changed |= set(obl.field_deltas)
        reasons.extend(obl.reasons)
        if _LEVEL_ORDER[obl.max_materiality] > _LEVEL_ORDER[level]:
            level = obl.max_materiality

    detail = "; ".join(r["detail"] for r in reasons) if reasons else "obligation-level change"
    merged = MaterialityVerdict(level, tuple(reasons), detail)
    row = _to_row(ChangeKind.MODIFIED, sorted(changed), merged, old, new, similarity)
    if obl is not None:
        row.citations["obligation_compare"] = {
            "obligations_old": obl.n_old,
            "obligations_new": obl.n_new,
            "matched": obl.n_matched,
            "field_deltas": obl.field_deltas,
            "created": obl.created,
            "removed": obl.removed,
        }
    return row


def diff_created(new: SectionUnit) -> ChangeRow:
    fields = _fields_from_section(new, with_risk=True)
    verdict = classify_change(None, fields)
    materiality = assess_materiality(verdict, None, fields)
    return _to_row(ChangeKind.CREATED, [], materiality, None, new, None)


def diff_removed(old: SectionUnit) -> ChangeRow:
    fields = _fields_from_section(old, with_risk=True)
    verdict = classify_change(fields, None)
    materiality = assess_materiality(verdict, fields, None)
    return _to_row(ChangeKind.REMOVED, [], materiality, old, None, None)
