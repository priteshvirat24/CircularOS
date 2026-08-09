"""Pure known-answer tests for Tenant A mapping and evidence freshness rules."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date

import pytest

from packages.regulatory_core.models.compliance import EvidenceStatus
from scripts.build_tenant_a_controls import (
    CONTROL_CATALOG,
    ObligationFact,
    calculate_freshness,
    plan_control_freshness,
    plan_mappings,
)


def _fact(index: int, text: str) -> ObligationFact:
    return ObligationFact(uuid.UUID(int=index), "Stock Broker", "", "", text)


def test_catalogue_is_compact_unique_and_every_rule_matches() -> None:
    assert len(CONTROL_CATALOG) == 15
    assert len({item.key for item in CONTROL_CATALOG}) == 15
    facts = tuple(_fact(index + 1, spec.match_any[0]) for index, spec in enumerate(CONTROL_CATALOG))
    plans = plan_mappings(facts)
    assert len(plans) == 15
    assert Counter(item.control_key for item in plans) == Counter(
        item.key for item in CONTROL_CATALOG
    )


def test_first_matching_control_disposes_overlap_deterministically() -> None:
    fact = _fact(1, "verify antecedents and change in control")
    plans = plan_mappings((fact,))
    assert len(plans) == 1
    assert plans[0].control_key == "fit_proper_screening"
    assert plans[0].matched_term == "verify antecedents"


def test_freshness_is_computed_from_dates_and_frequency() -> None:
    as_of = date(2026, 8, 9)
    valid = calculate_freshness(date(2026, 7, 20), 31, as_of)
    stale = calculate_freshness(date(2026, 6, 1), 31, as_of)
    assert valid.valid_until == date(2026, 8, 20)
    assert valid.status == EvidenceStatus.VALID
    assert stale.valid_until == date(2026, 7, 2)
    assert stale.status == EvidenceStatus.STALE

    by_key = {item.key: item for item in CONTROL_CATALOG}
    account = plan_control_freshness(by_key["account_nomenclature"], as_of)
    dossier = plan_control_freshness(by_key["registration_dossier"], as_of)
    assert account is not None and account.status == EvidenceStatus.STALE
    assert dossier is None


@pytest.mark.parametrize("days", (0, -1))
def test_freshness_rejects_nonpositive_windows(days: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        calculate_freshness(date(2026, 8, 1), days, date(2026, 8, 9))


def test_freshness_rejects_future_collection() -> None:
    with pytest.raises(ValueError, match="after as_of"):
        calculate_freshness(date(2026, 8, 10), 31, date(2026, 8, 9))
