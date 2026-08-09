"""Change classification and materiality — the deterministic verdict core.

Pure functions only. Given the structured fields of an old and/or new obligation, decide
whether the obligation was CREATED / MODIFIED / REMOVED, exactly which fields changed, and
how material the change is. Materiality is the join (max) over fired typed rules on the
severity lattice ``NONE ≤ LOW ≤ MEDIUM ≤ HIGH`` (MATHEMATICAL_FOUNDATIONS.md §3–§4).

No I/O, no randomness, no time-dependence: same input → same output, always.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace  # noqa: F401  (replace re-exported for tests)

# ── Data shapes ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ObligationFields:
    """The structured, comparable fields of a single obligation.

    Text fields compare by normalized string equality; list fields by set equality of
    normalized items. ``risk_level`` is an optional hint (one of critical/high/medium/low/
    informational) used only by the CREATED-materiality rule; it never affects classification.
    """

    normalized_obligation: str = ""
    actor: str | None = None
    action: str | None = None
    object: str | None = None
    conditions: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()
    frequency: str | None = None
    deadline: str | None = None
    evidence_requirement: str | None = None
    penalty_reference: str | None = None
    applicability: tuple[str, ...] = ()
    risk_level: str | None = None


class ChangeKind(enum.StrEnum):
    CREATED = "created"
    MODIFIED = "modified"
    REMOVED = "removed"


@dataclass(frozen=True)
class ChangeVerdict:
    kind: ChangeKind
    changed_fields: tuple[str, ...]  # empty for CREATED/REMOVED; the differing fields for MODIFIED
    explanation: str

    @property
    def is_substantive(self) -> bool:
        """MODIFIED with no differing fields means 'unchanged' — the caller emits no row."""
        return self.kind != ChangeKind.MODIFIED or bool(self.changed_fields)


class MaterialityLevel(enum.StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_LEVEL_ORDER = {
    MaterialityLevel.NONE: 0,
    MaterialityLevel.LOW: 1,
    MaterialityLevel.MEDIUM: 2,
    MaterialityLevel.HIGH: 3,
}


def _join(levels: list[MaterialityLevel]) -> MaterialityLevel:
    """Least upper bound on the severity chain — i.e. the max fired severity."""
    if not levels:
        return MaterialityLevel.NONE
    return max(levels, key=lambda lv: _LEVEL_ORDER[lv])


@dataclass(frozen=True)
class MaterialityVerdict:
    level: MaterialityLevel
    reasons: tuple[dict, ...]  # [{"rule", "fields", "detail"}]
    explanation: str

    @property
    def requires_confirmation(self) -> bool:
        return _LEVEL_ORDER[self.level] >= _LEVEL_ORDER[MaterialityLevel.MEDIUM]


# ── Field normalization & comparison ───────────────────────────────────────────

_TEXT_FIELDS = (
    "normalized_obligation",
    "actor",
    "action",
    "object",
    "frequency",
    "deadline",
    "evidence_requirement",
    "penalty_reference",
)
_LIST_FIELDS = ("conditions", "exceptions", "applicability")


def _norm_text(v: str | None) -> str:
    if not v:
        return ""
    return re.sub(r"\s+", " ", v).strip().casefold()


def _norm_set(items: Iterable[str | None] | None) -> frozenset[str]:
    if not items:
        return frozenset()
    return frozenset(_norm_text(x) for x in items if _norm_text(x))


def _diff_fields(old: ObligationFields, new: ObligationFields) -> list[str]:
    changed: list[str] = []
    for f in _TEXT_FIELDS:
        if _norm_text(getattr(old, f)) != _norm_text(getattr(new, f)):
            changed.append(f)
    for f in _LIST_FIELDS:
        if _norm_set(getattr(old, f)) != _norm_set(getattr(new, f)):
            changed.append(f)
    return changed


# ── Classification (MATHEMATICAL_FOUNDATIONS.md §3) ─────────────────────────────


def classify_change(
    old: ObligationFields | None,
    new: ObligationFields | None,
) -> ChangeVerdict:
    """Classify an old/new obligation pair as CREATED / MODIFIED / REMOVED.

    - ``old is None`` → CREATED. ``new is None`` → REMOVED.
    - Both present → MODIFIED with the set of differing fields. If no field differs, the
      returned verdict has empty ``changed_fields`` (``is_substantive`` is False) and the
      caller must treat it as unchanged (no change row). Clause-number/formatting-only
      differences are handled by the structural layer, not here.
    """
    if old is None and new is None:
        raise ValueError("classify_change requires at least one of old/new")
    if old is None:
        return ChangeVerdict(ChangeKind.CREATED, (), "obligation present in new document only")
    if new is None:
        return ChangeVerdict(ChangeKind.REMOVED, (), "obligation present in old document only")

    changed = _diff_fields(old, new)
    if not changed:
        return ChangeVerdict(
            ChangeKind.MODIFIED,
            (),
            "all structured fields equal — not a substantive change",
        )
    return ChangeVerdict(
        ChangeKind.MODIFIED,
        tuple(changed),
        f"structured fields changed: {', '.join(changed)}",
    )


# ── Deterministic value parsers for the ordered rules ───────────────────────────


def _parse_deadline_days(v: str | None) -> int | None:
    """Map common SEBI deadline phrasings to a day count (smaller = stricter).

    Returns ``None`` when the value is absent or genuinely incomparable (event-triggered,
    periodic, or unrecognized) — the caller then defaults to MEDIUM rather than guessing.
    """
    if not v:
        return None
    s = v.strip().casefold()
    # Same-day / immediate forms.
    if re.search(
        r"\b(t\s*\+\s*0|same day|end of (the )?(trading )?day|eod|immediate(ly)?|intra-?day|real[- ]?time)\b",
        s,
    ):
        return 0
    m = re.search(r"\bt\s*\+\s*(\d+)\b", s)  # T+1, T + 2
    if m:
        return int(m.group(1))
    m = re.search(r"\bwithin\s+(\d+)\s+day", s)  # within 7 days
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d+)\s+(working|business|calendar)?\s*day", s)  # 15 days / 7 working days
    if m:
        return int(m.group(1))
    return None  # periodic ("quarterly deadline"), event-triggered, or unknown → incomparable


# frequency ranked by how often it recurs; higher rank = more frequent.
_FREQ_RANK = [
    (r"\b(real[- ]?time|continuous|intra-?day)\b", 7),
    (r"\b(daily|every day|per day|t\s*\+\s*0)\b", 6),
    (r"\b(weekly|every week|per week)\b", 5),
    (r"\b(fortnight|bi-?weekly|every two weeks)\b", 4),
    (r"\b(monthly|every month|per month)\b", 3),
    (r"\b(quarter|quarterly)\b", 2),
    (r"\b(half[- ]?year|semi[- ]?annual|bi-?annual)\b", 1),
    (r"\b(annual|yearly|per year|per annum)\b", 0),
]


def _parse_frequency_rank(v: str | None) -> int | None:
    if not v:
        return None
    s = v.strip().casefold()
    for pat, rank in _FREQ_RANK:
        if re.search(pat, s):
            return rank
    return None


def _is_high_risk(level: str | None) -> bool:
    return (level or "").strip().casefold() in {"high", "critical"}


# ── Materiality (MATHEMATICAL_FOUNDATIONS.md §4) ────────────────────────────────

# Only these fields are "material"; a change confined outside them is cosmetic/clarifying.
_MATERIAL_FIELDS = {
    "actor",
    "applicability",
    "deadline",
    "frequency",
    "evidence_requirement",
    "penalty_reference",
    "conditions",
    "exceptions",
    "action",
}

# Regulatory categories SEBI has formally discontinued. When a text-only change merely drops
# one of these from an obligation's wording (and no structured field changed), it is a
# terminology cleanup, not a change to the underlying duty — LOW, with an explicit reason.
# Keyed by normalized (casefolded, dash-folded) form → human-readable label.
_DISCONTINUED_TERMS = {
    "sub-broker": "Sub-Brokers",
    "sub-brokers": "Sub-Brokers",
}


def _discontinued_terms_removed(old: ObligationFields, new: ObligationFields) -> list[str]:
    """Labels of discontinued categories present in old wording but absent from new."""
    old_text = f"{_norm_text(old.normalized_obligation)} {_norm_text(old.object)}"
    new_text = f"{_norm_text(new.normalized_obligation)} {_norm_text(new.object)}"
    removed: list[str] = []
    for term, label in _DISCONTINUED_TERMS.items():
        if term in old_text and term not in new_text and label not in removed:
            removed.append(label)
    return removed


def assess_materiality(
    change: ChangeVerdict,
    old: ObligationFields | None,
    new: ObligationFields | None,
) -> MaterialityVerdict:
    """Score materiality as the join of all fired typed rules on the severity lattice.

    Every fired rule contributes a ``{rule, fields, detail}`` reason. The deadline rule uses
    a partial order on deadlines (incomparable/unparseable ⇒ MEDIUM, never silently NONE).
    """
    reasons: list[dict] = []
    levels: list[MaterialityLevel] = []

    def fire(rule: str, level: MaterialityLevel, fields: Sequence[str], detail: str) -> None:
        reasons.append({"rule": rule, "fields": list(fields), "detail": detail})
        levels.append(level)

    if change.kind is ChangeKind.CREATED:
        if new is not None and _is_high_risk(new.risk_level):
            fire(
                "new_high_risk_obligation",
                MaterialityLevel.HIGH,
                [],
                f"new obligation with {new.risk_level} risk",
            )
        else:
            fire(
                "new_obligation",
                MaterialityLevel.MEDIUM,
                [],
                "new obligation created — surface for confirmation",
            )
        return _finalize(levels, reasons)

    if change.kind is ChangeKind.REMOVED:
        fire(
            "obligation_removed",
            MaterialityLevel.MEDIUM,
            [],
            "obligation removed — surface for confirmation",
        )
        return _finalize(levels, reasons)

    # MODIFIED
    changed = set(change.changed_fields)
    if not changed:
        # No field differs → unchanged/cosmetic. NONE.
        return MaterialityVerdict(
            MaterialityLevel.NONE,
            (),
            "no substantive field changed",
        )

    assert old is not None and new is not None  # MODIFIED always has both

    # deadline_tightened (partial order; incomparable ⇒ MEDIUM)
    if "deadline" in changed:
        od, nd = _parse_deadline_days(old.deadline), _parse_deadline_days(new.deadline)
        if od is not None and nd is not None:
            if nd < od:
                fire(
                    "deadline_tightened",
                    MaterialityLevel.HIGH,
                    ["deadline"],
                    f"deadline tightened: {old.deadline} → {new.deadline}",
                )
            elif nd > od:
                fire(
                    "deadline_relaxed",
                    MaterialityLevel.MEDIUM,
                    ["deadline"],
                    f"deadline relaxed: {old.deadline} → {new.deadline}",
                )
            else:
                fire(
                    "deadline_reworded",
                    MaterialityLevel.LOW,
                    ["deadline"],
                    f"deadline reworded, same strictness: {old.deadline} → {new.deadline}",
                )
        else:
            fire(
                "deadline_changed_incomparable",
                MaterialityLevel.MEDIUM,
                ["deadline"],
                f"deadline changed (incomparable): {old.deadline} → {new.deadline}",
            )

    # actor_expanded (new actor/applicability set is a strict superset)
    if "actor" in changed or "applicability" in changed:
        old_actors = _norm_set(list(old.applicability) + ([old.actor] if old.actor else []))
        new_actors = _norm_set(list(new.applicability) + ([new.actor] if new.actor else []))
        added = new_actors - old_actors
        if added and old_actors < new_actors:
            fire(
                "actor_expanded",
                MaterialityLevel.HIGH,
                [f for f in ("actor", "applicability") if f in changed],
                f"actor set expanded: added {sorted(added)}",
            )
        else:
            fire(
                "actor_changed",
                MaterialityLevel.MEDIUM,
                [f for f in ("actor", "applicability") if f in changed],
                "responsible actor / applicability changed",
            )

    # new_evidence_requirement
    if "evidence_requirement" in changed:
        if _norm_text(new.evidence_requirement) and not _norm_text(old.evidence_requirement):
            fire(
                "new_evidence_requirement",
                MaterialityLevel.HIGH,
                ["evidence_requirement"],
                "a new evidence requirement was added",
            )
        else:
            fire(
                "evidence_requirement_changed",
                MaterialityLevel.MEDIUM,
                ["evidence_requirement"],
                "evidence requirement changed",
            )

    # penalty_changed
    if "penalty_reference" in changed:
        if _norm_text(new.penalty_reference) and not _norm_text(old.penalty_reference):
            fire(
                "penalty_introduced",
                MaterialityLevel.HIGH,
                ["penalty_reference"],
                "a penalty reference was introduced",
            )
        else:
            fire(
                "penalty_changed",
                MaterialityLevel.MEDIUM,
                ["penalty_reference"],
                "penalty reference changed",
            )

    # frequency_increased
    if "frequency" in changed:
        of, nf = _parse_frequency_rank(old.frequency), _parse_frequency_rank(new.frequency)
        if of is not None and nf is not None and nf > of:
            fire(
                "frequency_increased",
                MaterialityLevel.MEDIUM,
                ["frequency"],
                f"reporting frequency increased: {old.frequency} → {new.frequency}",
            )
        elif of is not None and nf is not None and nf < of:
            fire(
                "frequency_decreased",
                MaterialityLevel.LOW,
                ["frequency"],
                f"reporting frequency decreased: {old.frequency} → {new.frequency}",
            )
        else:
            fire(
                "frequency_changed",
                MaterialityLevel.MEDIUM,
                ["frequency"],
                f"reporting frequency changed: {old.frequency} → {new.frequency}",
            )

    # conditions_changed / exceptions_changed
    cond_fields = [f for f in ("conditions", "exceptions") if f in changed]
    if cond_fields:
        fire(
            "conditions_changed",
            MaterialityLevel.MEDIUM,
            cond_fields,
            "conditions/exceptions changed materially",
        )

    # action_changed (the core verb of the obligation)
    if "action" in changed:
        fire("action_changed", MaterialityLevel.MEDIUM, ["action"], "the required action changed")

    # Descriptive-text-only change (no material field fired). Distinguish a terminology cleanup
    # (a discontinued category dropped from the wording) from a generic wording clarification —
    # both LOW, but the cleanup carries a precise, regulator-legible reason.
    if not levels:
        text_only = sorted(changed - _MATERIAL_FIELDS)
        removed = _discontinued_terms_removed(old, new)
        if removed:
            fire(
                "terminology_cleanup",
                MaterialityLevel.LOW,
                text_only,
                f"terminology cleanup: removed discontinued category "
                f"{', '.join(repr(t) for t in removed)}; no change to the underlying duty",
            )
        else:
            fire(
                "wording_clarified",
                MaterialityLevel.LOW,
                text_only,
                "wording clarified; no structured field changed",
            )

    return _finalize(levels, reasons)


def _finalize(levels: list[MaterialityLevel], reasons: list[dict]) -> MaterialityVerdict:
    level = _join(levels)
    detail = "; ".join(r["detail"] for r in reasons) if reasons else "no material rule fired"
    return MaterialityVerdict(level, tuple(reasons), detail)
