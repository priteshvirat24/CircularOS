"""Unit tests for the pure Policy Decision Engine: classify_change + assess_materiality.

Covers the full branch matrix required by the Phase-2 exit gate:
CREATED / MODIFIED / REMOVED, deadline-tighten, actor-expand, new-evidence, penalty-change,
frequency, cosmetic-only, wording-clarified — plus the materiality monotonicity invariant.
"""

from __future__ import annotations

import dataclasses

import pytest

from packages.policy_engine.changes import (
    ChangeKind,
    MaterialityLevel,
    ObligationFields,
    assess_materiality,
    classify_change,
)


def mk(**kw) -> ObligationFields:
    return ObligationFields(**kw)


# ── classify_change ─────────────────────────────────────────────────────────────

def test_created():
    v = classify_change(None, mk(normalized_obligation="do X"))
    assert v.kind is ChangeKind.CREATED
    assert v.changed_fields == ()
    assert v.is_substantive


def test_removed():
    v = classify_change(mk(normalized_obligation="do X"), None)
    assert v.kind is ChangeKind.REMOVED
    assert v.is_substantive


def test_both_none_raises():
    with pytest.raises(ValueError):
        classify_change(None, None)


def test_modified_reports_changed_fields():
    old = mk(actor="TM", deadline="T+1", normalized_obligation="report margin")
    new = mk(actor="TM", deadline="T+0", normalized_obligation="report margin")
    v = classify_change(old, new)
    assert v.kind is ChangeKind.MODIFIED
    assert v.changed_fields == ("deadline",)
    assert v.is_substantive


def test_identical_is_not_substantive():
    a = mk(actor="TM", deadline="T+1", normalized_obligation="report margin",
          conditions=("x",))
    b = mk(actor="TM", deadline="T+1", normalized_obligation="report margin",
          conditions=("x",))
    v = classify_change(a, b)
    assert v.kind is ChangeKind.MODIFIED
    assert v.changed_fields == ()
    assert not v.is_substantive  # caller emits no row


def test_whitespace_and_case_are_not_changes():
    a = mk(actor="Stock  Broker", normalized_obligation="Report  Margin")
    b = mk(actor="stock broker", normalized_obligation="report margin")
    assert classify_change(a, b).changed_fields == ()


def test_list_field_set_equality_ignores_order():
    a = mk(applicability=("TM", "CM"))
    b = mk(applicability=("CM", "TM"))
    assert classify_change(a, b).changed_fields == ()


# ── assess_materiality: CREATED / REMOVED ────────────────────────────────────────

def test_created_high_risk_is_high():
    v = classify_change(None, mk(normalized_obligation="new audit rule", risk_level="high"))
    m = assess_materiality(v, None, mk(risk_level="high"))
    assert m.level is MaterialityLevel.HIGH
    assert m.requires_confirmation
    assert any(r["rule"] == "new_high_risk_obligation" for r in m.reasons)


def test_created_default_is_medium():
    new = mk(normalized_obligation="new facilitation")
    v = classify_change(None, new)
    m = assess_materiality(v, None, new)
    assert m.level is MaterialityLevel.MEDIUM
    assert m.requires_confirmation


def test_removed_is_medium():
    old = mk(normalized_obligation="old rule")
    v = classify_change(old, None)
    m = assess_materiality(v, old, None)
    assert m.level is MaterialityLevel.MEDIUM


# ── assess_materiality: MODIFIED rules ───────────────────────────────────────────

def test_deadline_tightened_high():
    old, new = mk(deadline="T+1"), mk(deadline="T+0")
    m = assess_materiality(classify_change(old, new), old, new)
    assert m.level is MaterialityLevel.HIGH
    assert any(r["rule"] == "deadline_tightened" for r in m.reasons)


def test_deadline_relaxed_medium():
    old, new = mk(deadline="T+1"), mk(deadline="T+2")
    m = assess_materiality(classify_change(old, new), old, new)
    assert m.level is MaterialityLevel.MEDIUM
    assert any(r["rule"] == "deadline_relaxed" for r in m.reasons)


def test_deadline_within_days_parsed():
    old, new = mk(deadline="within 15 days"), mk(deadline="within 7 days")
    m = assess_materiality(classify_change(old, new), old, new)
    assert m.level is MaterialityLevel.HIGH


def test_deadline_incomparable_defaults_medium():
    # periodic/event-triggered deadline can't be ordered → surface to human, never NONE.
    old, new = mk(deadline="quarterly review"), mk(deadline="on occurrence of event")
    m = assess_materiality(classify_change(old, new), old, new)
    assert m.level is MaterialityLevel.MEDIUM
    assert any(r["rule"] == "deadline_changed_incomparable" for r in m.reasons)


def test_actor_expanded_high():
    old = mk(applicability=("Trading Member",))
    new = mk(applicability=("Trading Member", "Clearing Member"))
    m = assess_materiality(classify_change(old, new), old, new)
    assert m.level is MaterialityLevel.HIGH
    assert any(r["rule"] == "actor_expanded" for r in m.reasons)


def test_actor_changed_not_expanded_medium():
    old = mk(actor="Trading Member")
    new = mk(actor="Clearing Member")
    m = assess_materiality(classify_change(old, new), old, new)
    assert m.level is MaterialityLevel.MEDIUM
    assert any(r["rule"] == "actor_changed" for r in m.reasons)


def test_new_evidence_requirement_high():
    old = mk(evidence_requirement=None)
    new = mk(evidence_requirement="maintain a monitoring log")
    m = assess_materiality(classify_change(old, new), old, new)
    assert m.level is MaterialityLevel.HIGH
    assert any(r["rule"] == "new_evidence_requirement" for r in m.reasons)


def test_penalty_introduced_high_vs_changed_medium():
    m1 = assess_materiality(
        classify_change(mk(penalty_reference=None), mk(penalty_reference="Sec 15A")),
        mk(penalty_reference=None), mk(penalty_reference="Sec 15A"),
    )
    assert m1.level is MaterialityLevel.HIGH
    m2 = assess_materiality(
        classify_change(mk(penalty_reference="Sec 15A"), mk(penalty_reference="Sec 15B")),
        mk(penalty_reference="Sec 15A"), mk(penalty_reference="Sec 15B"),
    )
    assert m2.level is MaterialityLevel.MEDIUM


def test_frequency_increased_medium():
    old, new = mk(frequency="monthly"), mk(frequency="daily")
    m = assess_materiality(classify_change(old, new), old, new)
    assert m.level is MaterialityLevel.MEDIUM
    assert any(r["rule"] == "frequency_increased" for r in m.reasons)


def test_wording_clarified_low():
    old = mk(normalized_obligation="brokers shall report", object="the margin")
    new = mk(normalized_obligation="brokers must report", object="the margin amount")
    v = classify_change(old, new)
    assert set(v.changed_fields) <= {"normalized_obligation", "object"}
    m = assess_materiality(v, old, new)
    assert m.level is MaterialityLevel.LOW
    assert any(r["rule"] == "wording_clarified" for r in m.reasons)


def test_terminology_cleanup_low_with_explicit_reason():
    # The real §31→§32 case: a discontinued category ("Sub-Brokers") dropped from the title,
    # no structured field changed. LOW, tagged as terminology cleanup (not a substantive change).
    old = mk(normalized_obligation="Review of norms relating to trading by Members/ Sub-Brokers",
             object="Review of norms relating to trading by Members/ Sub-Brokers")
    new = mk(normalized_obligation="Review of norms relating to trading by Members",
             object="Review of norms relating to trading by Members")
    v = classify_change(old, new)
    m = assess_materiality(v, old, new)
    assert m.level is MaterialityLevel.LOW
    reason = next(r for r in m.reasons if r["rule"] == "terminology_cleanup")
    assert "Sub-Brokers" in reason["detail"]
    assert "no change to the underlying duty" in reason["detail"]


def test_wording_change_without_discontinued_term_is_plain_clarification():
    old = mk(normalized_obligation="brokers shall report", object="the margin")
    new = mk(normalized_obligation="brokers must report", object="the margin amount")
    m = assess_materiality(classify_change(old, new), old, new)
    assert m.level is MaterialityLevel.LOW
    assert {r["rule"] for r in m.reasons} == {"wording_clarified"}


def test_cosmetic_no_field_change_is_none():
    a = mk(normalized_obligation="same", actor="TM")
    v = classify_change(a, a)
    m = assess_materiality(v, a, a)
    assert m.level is MaterialityLevel.NONE
    assert not m.requires_confirmation


# ── materiality is the MAX over fired rules; reasons collect all ─────────────────

def test_multiple_rules_take_max_and_collect_all():
    old = mk(deadline="T+1", frequency="monthly")
    new = mk(deadline="T+0", frequency="daily")
    m = assess_materiality(classify_change(old, new), old, new)
    assert m.level is MaterialityLevel.HIGH  # deadline HIGH dominates frequency MEDIUM
    fired = {r["rule"] for r in m.reasons}
    assert "deadline_tightened" in fired and "frequency_increased" in fired


# ── monotonicity invariant (MATHEMATICAL_FOUNDATIONS.md §4) ──────────────────────

def _level_value(m) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3}[m.level.value]


def test_materiality_monotonic_superset_of_features():
    """A change with a superset of material features has μ(c') ≥ μ(c)."""
    base_old = mk(frequency="monthly")
    base_new = mk(frequency="daily")
    base = assess_materiality(classify_change(base_old, base_new), base_old, base_new)

    # c' adds a tightened deadline on top of the frequency change.
    sup_old = dataclasses.replace(base_old, deadline="T+1")
    sup_new = dataclasses.replace(base_new, deadline="T+0")
    sup = assess_materiality(classify_change(sup_old, sup_new), sup_old, sup_new)

    assert _level_value(sup) >= _level_value(base)


def test_materiality_adding_features_never_lowers():
    """Sweep: starting from a MEDIUM change, adding any further material feature never lowers."""
    old = mk(frequency="monthly")
    new = mk(frequency="daily")
    m0 = _level_value(assess_materiality(classify_change(old, new), old, new))
    additions = [
        ({"deadline": "T+1"}, {"deadline": "T+0"}),
        ({"evidence_requirement": None}, {"evidence_requirement": "log"}),
        ({"penalty_reference": None}, {"penalty_reference": "Sec 15A"}),
        ({"applicability": ("TM",)}, {"applicability": ("TM", "CM")}),
    ]
    for oadd, nadd in additions:
        o2 = dataclasses.replace(old, **oadd)
        n2 = dataclasses.replace(new, **nadd)
        m = _level_value(assess_materiality(classify_change(o2, n2), o2, n2))
        assert m >= m0
