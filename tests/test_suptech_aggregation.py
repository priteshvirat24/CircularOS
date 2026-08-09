"""Known-answer tests for the pure deterministic SupTech calculations."""

from __future__ import annotations

import uuid
from datetime import date

from packages.suptech.aggregation import (
    build_adoption_view,
    build_gap_view,
    build_posture_view,
)
from packages.suptech.types import (
    ChangeInput,
    EvidenceInput,
    IntermediaryInput,
    MarketInput,
    ObligationInput,
)


def _id(value: int) -> uuid.UUID:
    return uuid.UUID(int=value)


def _market() -> MarketInput:
    obligations = (
        ObligationInput(_id(1), "high"),
        ObligationInput(_id(2), "medium"),
        ObligationInput(_id(3), "low"),
    )
    changes = (
        ChangeInput(_id(10), "§17", "System audit supervision", "high"),
        ChangeInput(_id(11), "§71", "SBU framework", "medium"),
    )
    return MarketInput(
        as_of=date(2026, 8, 9),
        circular_id=_id(99),
        circular_title="June circular",
        changes=changes,
        intermediaries=(
            IntermediaryInput(
                id=_id(20),
                name="Real A",
                seeded=False,
                obligations=obligations,
                controlled_obligation_ids=frozenset({_id(1), _id(2), _id(3)}),
                evidence=(
                    EvidenceInput(_id(1), "valid", date(2027, 1, 1)),
                    EvidenceInput(_id(2), "stale", date(2025, 1, 1)),
                ),
                completed_change_ids=frozenset({_id(10)}),
            ),
            IntermediaryInput(
                id=_id(21),
                name="Seeded B",
                seeded=True,
                obligations=obligations,
                controlled_obligation_ids=frozenset({_id(1)}),
                evidence=(EvidenceInput(_id(1), "valid", None),),
                completed_change_ids=frozenset({_id(10), _id(11)}),
            ),
        ),
    )


def test_posture_known_answer() -> None:
    result = build_posture_view(_market())
    assert result["market_rollup"] == {
        "intermediaries": 2,
        "real_intermediaries": 1,
        "seeded_intermediaries": 1,
        "coverage_percentage": 33.33,
        "evidence_freshness": {"valid": 2, "stale": 1, "missing": 3},
        "open_gaps": 4,
        "latest_circular_adoption_percentage": 75.0,
    }
    by_name = {item["name"]: item for item in result["intermediaries"]}
    assert by_name["Real A"]["coverage"]["percentage"] == 33.33
    assert by_name["Real A"]["evidence_freshness"] == {
        "valid": 1,
        "stale": 1,
        "missing": 1,
    }
    assert by_name["Seeded B"]["seeded"] is True


def test_adoption_and_both_gap_kinds() -> None:
    market = _market()
    adoption = build_adoption_view(market)
    section_71 = next(item for item in adoption["changes"] if item["reference"] == "§71")
    assert section_71["adoption_percentage"] == 50.0
    assert section_71["gap_key"] == f"change:{_id(11)}"

    obligation_gap = build_gap_view(market, f"obligation:{_id(2)}")
    assert obligation_gap is not None
    assert obligation_gap["affected_intermediaries"] == 2
    by_name = {item["name"]: item for item in obligation_gap["intermediaries"]}
    assert by_name["Real A"]["gap_types"] == ["evidence_stale"]
    assert by_name["Seeded B"]["gap_types"] == ["control_missing", "evidence_missing"]

    adoption_gap = build_gap_view(market, f"change:{_id(11)}")
    assert adoption_gap is not None
    assert adoption_gap["affected_intermediaries"] == 1
    assert adoption_gap["intermediaries"][0]["name"] == "Real A"


def test_unknown_gap_is_absent() -> None:
    assert build_gap_view(_market(), "change:missing") is None
