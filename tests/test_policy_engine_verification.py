"""Branch and invariant tests for the Phase-3 pure Policy Decision Engine."""

from __future__ import annotations

from dataclasses import replace

import pytest

from packages.policy_engine.changes import MaterialityLevel
from packages.policy_engine.citations import MatchType, verify_citation
from packages.policy_engine.confidence import (
    DEFAULT_CONFIDENCE_PARAMS,
    ConfidenceBand,
    ExtractionSignals,
    aggregate_confidence,
)
from packages.policy_engine.impact import (
    ImpactChange,
    OrgGraph,
    OrgNode,
    OrgNodeKind,
    resolve_blast_radius,
)


def test_verify_citation_exact_returns_first_original_span() -> None:
    source = "Broker shall report. Broker shall report."
    verdict = verify_citation("Broker shall report", source)
    assert verdict.match_type is MatchType.EXACT
    assert verdict.valid is True
    assert verdict.score == 1.0
    assert verdict.span == (0, 19)


def test_verify_citation_normalized_maps_unicode_whitespace_to_original_span() -> None:
    source = "Prefix — STOCK\nBROKER shall submit the report, promptly. Suffix"
    quote = "stock broker shall submit the report promptly"
    verdict = verify_citation(quote, source)
    assert verdict.match_type is MatchType.NORMALIZED
    assert verdict.valid is True
    assert verdict.span is not None
    assert (
        source[verdict.span[0] : verdict.span[1]]
        == "STOCK\nBROKER shall submit the report, promptly"
    )


def test_verify_citation_unicode_emoji_and_rtl_exact() -> None:
    source = "Evidence ✅ shall be retained. يجب الحفظ"
    assert verify_citation("Evidence ✅ shall be retained", source).valid is True
    rtl = verify_citation("يجب الحفظ", source)
    assert rtl.match_type is MatchType.EXACT
    assert rtl.span == (30, 39)


def test_verify_citation_fuzzy_accepts_ocr_noise() -> None:
    source = "The stock broker shall maintain complete electronic records for seven years."
    quote = "The stock broker shall maintain completc electronic records for seven years."
    verdict = verify_citation(quote, source)
    assert verdict.match_type is MatchType.FUZZY
    assert verdict.score >= 0.95
    assert verdict.span is not None
    assert source[verdict.span[0] : verdict.span[1]] == source.rstrip(".")


@pytest.mark.parametrize("quote", ["", "   ", "This invented duty does not exist"])
def test_verify_citation_not_found_is_always_invalid(quote: str) -> None:
    verdict = verify_citation(quote, "Stock brokers shall preserve records.")
    assert verdict.match_type is MatchType.NOT_FOUND
    assert verdict.valid is False
    assert verdict.span is None


def test_verify_citation_near_miss_below_threshold_is_not_found() -> None:
    source = "Stock brokers shall submit monthly reports to every exchange."
    quote = "Stock custodians must file annual returns with every depository."
    verdict = verify_citation(quote, source)
    assert verdict.match_type is MatchType.NOT_FOUND
    assert verdict.score < 0.95


def _signals(**overrides: object) -> ExtractionSignals:
    values: dict[str, object] = {
        "citations_all_valid": True,
        "citation_min_score": 1.0,
        "entailment": "entailment",
        "critic_has_objection": False,
        "model_self_confidence": 0.9,
        "difficulty": "easy",
    }
    values.update(overrides)
    return ExtractionSignals(**values)  # type: ignore[arg-type]


def test_confidence_high_and_factors_are_visible() -> None:
    verdict = aggregate_confidence(_signals())
    assert verdict.band is ConfidenceBand.HIGH
    assert verdict.score >= 0.8
    assert any("citation score" in factor for factor in verdict.contributing_factors)
    assert verdict.params_version == "phase3-default-unfitted"


def test_confidence_medium_from_neutral_difficult_signal() -> None:
    verdict = aggregate_confidence(
        _signals(
            citation_min_score=0.96,
            entailment="neutral",
            model_self_confidence=0.7,
            difficulty="hard",
        )
    )
    assert verdict.band is ConfidenceBand.MEDIUM


def test_confidence_invalid_citation_hard_gate_forces_zero() -> None:
    verdict = aggregate_confidence(_signals(citations_all_valid=False))
    assert verdict.score == 0.0
    assert verdict.band is ConfidenceBand.LOW
    assert "NOT_FOUND" in verdict.contributing_factors[0]


def test_confidence_contradiction_cannot_be_rescued() -> None:
    verdict = aggregate_confidence(_signals(entailment="contradiction"))
    assert verdict.score == 0.0
    assert verdict.band is ConfidenceBand.LOW


def test_confidence_uses_passed_parameters() -> None:
    params = replace(DEFAULT_CONFIDENCE_PARAMS, intercept=-20.0, version="test-fit")
    verdict = aggregate_confidence(_signals(), params)
    assert verdict.band is ConfidenceBand.LOW
    assert verdict.params_version == "test-fit"


def test_confidence_rejects_out_of_range_signals() -> None:
    with pytest.raises(ValueError, match="citation_min_score"):
        aggregate_confidence(_signals(citation_min_score=1.1))


def _graph() -> OrgGraph:
    return OrgGraph(
        nodes=(
            OrgNode("O-17", OrgNodeKind.OBLIGATION, "Section 17 cyber-resilience duty"),
            OrgNode("C-12", OrgNodeKind.CONTROL, "Cyber incident control"),
            OrgNode("P-4", OrgNodeKind.PROCESS, "Incident response process"),
            OrgNode("E-4", OrgNodeKind.EVIDENCE, "Weekly incident evidence"),
            OrgNode("D-7", OrgNodeKind.CALENDAR, "Weekly evidence deadline"),
        ),
        edges=(
            ("O-17", "C-12"),
            ("C-12", "P-4"),
            ("P-4", "E-4"),
            ("E-4", "D-7"),
            ("D-7", "C-12"),
        ),
    )


def test_blast_radius_reachability_named_path_and_cycle_safety() -> None:
    impact = resolve_blast_radius(
        ImpactChange("O-17", MaterialityLevel.HIGH, "change-17"), _graph()
    )
    assert impact.controls == ("C-12",)
    assert impact.processes == ("P-4",)
    assert impact.evidence_requirements == ("E-4",)
    assert impact.calendar_events == ("D-7",)
    assert impact.severity is MaterialityLevel.HIGH
    assert "obligation Section 17" in impact.explanation
    assert "calendar Weekly evidence deadline" in impact.explanation


def test_blast_radius_unknown_obligation_is_empty() -> None:
    impact = resolve_blast_radius(ImpactChange("missing", MaterialityLevel.MEDIUM), _graph())
    assert impact.controls == ()
    assert impact.named_paths == ()
    assert "no node" in impact.explanation


def test_blast_radius_can_begin_at_a_real_change_node() -> None:
    graph = OrgGraph(
        nodes=(
            OrgNode("change-1", OrgNodeKind.CHANGE, "System audit framework"),
            OrgNode("control-1", OrgNodeKind.CONTROL, "System audit control"),
            OrgNode("process-1", OrgNodeKind.PROCESS, "Audit supervision"),
        ),
        edges=(("change-1", "control-1"), ("control-1", "process-1")),
    )
    impact = resolve_blast_radius(
        ImpactChange("change-1", MaterialityLevel.HIGH, "change-1"), graph
    )
    assert impact.controls == ("control-1",)
    assert impact.processes == ("process-1",)
    assert impact.severity is MaterialityLevel.HIGH
