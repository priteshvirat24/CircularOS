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

from packages.diff_engine.normalize import canonical_title, clean_document_text
from packages.diff_engine.types import ChangeRow, SectionUnit
from packages.policy_engine.changes import (
    ChangeKind,
    MaterialityVerdict,
    ObligationFields,
    assess_materiality,
    classify_change,
)

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


def diff_pair(old: SectionUnit, new: SectionUnit, similarity: float) -> ChangeRow | None:
    """Compare a matched section pair. Returns a MODIFIED row, or None if not substantive."""
    verdict = classify_change(_fields_from_section(old), _fields_from_section(new))
    if not verdict.is_substantive:
        return None  # cosmetic / renumber-only — not reported
    materiality = assess_materiality(verdict, _fields_from_section(old), _fields_from_section(new))
    row = _to_row(ChangeKind.MODIFIED, verdict.changed_fields, materiality, old, new, similarity)
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
