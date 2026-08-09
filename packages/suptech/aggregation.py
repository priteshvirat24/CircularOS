"""Pure, deterministic SupTech calculations over aggregate-only inputs."""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date

from packages.suptech.types import EvidenceInput, IntermediaryInput, MarketInput

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_VALID_EVIDENCE = "valid"
_STALE_EVIDENCE = "stale"


def _percentage(numerator: int, denominator: int) -> float:
    return round((numerator / denominator * 100.0) if denominator else 0.0, 2)


def _severity(value: str | None) -> str:
    normalized = (value or "medium").lower()
    return normalized if normalized in _SEVERITY_ORDER else "medium"


def _evidence_state(evidence: tuple[EvidenceInput, ...], as_of: date) -> str:
    if any(
        item.status == _VALID_EVIDENCE and (item.valid_until is None or item.valid_until >= as_of)
        for item in evidence
    ):
        return "valid"
    if any(
        item.status == _STALE_EVIDENCE
        or (
            item.status == _VALID_EVIDENCE
            and item.valid_until is not None
            and item.valid_until < as_of
        )
        for item in evidence
    ):
        return "stale"
    return "missing"


@dataclass(frozen=True)
class _IntermediaryPosture:
    id: uuid.UUID
    name: str
    seeded: bool
    total: int
    covered: int
    freshness: dict[str, int]
    gaps: tuple[dict, ...]
    adopted: int
    adoption_total: int

    def public(self) -> dict:
        severity_counts = Counter(gap["severity"] for gap in self.gaps)
        return {
            "intermediary_id": str(self.id),
            "name": self.name,
            "seeded": self.seeded,
            "coverage": {
                "applicable_obligations": self.total,
                "covered_obligations": self.covered,
                "percentage": _percentage(self.covered, self.total),
            },
            "evidence_freshness": dict(self.freshness),
            "open_gaps": {
                "total": len(self.gaps),
                "by_severity": {
                    level: severity_counts[level] for level in ("critical", "high", "medium", "low")
                },
            },
            "latest_circular_adoption": {
                "operationalized": self.adopted,
                "tracked_changes": self.adoption_total,
                "percentage": _percentage(self.adopted, self.adoption_total),
            },
        }


def _posture(intermediary: IntermediaryInput, market: MarketInput) -> _IntermediaryPosture:
    evidence_by_obligation: dict[uuid.UUID, list[EvidenceInput]] = {}
    for item in intermediary.evidence:
        evidence_by_obligation.setdefault(item.obligation_id, []).append(item)

    freshness = {"valid": 0, "stale": 0, "missing": 0}
    gaps: list[dict] = []
    covered = 0
    for obligation in intermediary.obligations:
        state = _evidence_state(tuple(evidence_by_obligation.get(obligation.id, ())), market.as_of)
        freshness[state] += 1
        has_control = obligation.id in intermediary.controlled_obligation_ids
        if has_control and state == "valid":
            covered += 1
            continue
        gap_types: list[str] = []
        if not has_control:
            gap_types.append("control_missing")
        if state == "stale":
            gap_types.append("evidence_stale")
        elif state == "missing":
            gap_types.append("evidence_missing")
        gaps.append(
            {
                "gap_key": f"obligation:{obligation.id}",
                "obligation_id": str(obligation.id),
                "gap_types": gap_types,
                "severity": _severity(obligation.severity),
            }
        )

    adopted = sum(change.id in intermediary.completed_change_ids for change in market.changes)
    return _IntermediaryPosture(
        id=intermediary.id,
        name=intermediary.name,
        seeded=intermediary.seeded,
        total=len(intermediary.obligations),
        covered=covered,
        freshness=freshness,
        gaps=tuple(gaps),
        adopted=adopted,
        adoption_total=len(market.changes),
    )


def _all_postures(market: MarketInput) -> tuple[_IntermediaryPosture, ...]:
    return tuple(_posture(item, market) for item in market.intermediaries)


def build_posture_view(market: MarketInput) -> dict:
    """Return per-intermediary posture cards and a market-wide rollup."""
    postures = _all_postures(market)
    total_obligations = sum(item.total for item in postures)
    covered = sum(item.covered for item in postures)
    freshness = {
        state: sum(item.freshness[state] for item in postures)
        for state in ("valid", "stale", "missing")
    }
    adoption_slots = sum(item.adoption_total for item in postures)
    adopted = sum(item.adopted for item in postures)
    cards = sorted(
        (item.public() for item in postures),
        key=lambda item: (
            item["latest_circular_adoption"]["percentage"],
            item["coverage"]["percentage"],
            item["name"],
        ),
    )
    return {
        "as_of": market.as_of.isoformat(),
        "latest_circular": {
            "circular_id": str(market.circular_id),
            "title": market.circular_title,
            "tracked_changes": len(market.changes),
        },
        "market_rollup": {
            "intermediaries": len(postures),
            "real_intermediaries": sum(not item.seeded for item in postures),
            "seeded_intermediaries": sum(item.seeded for item in postures),
            "coverage_percentage": _percentage(covered, total_obligations),
            "evidence_freshness": freshness,
            "open_gaps": sum(len(item.gaps) for item in postures),
            "latest_circular_adoption_percentage": _percentage(adopted, adoption_slots),
        },
        "intermediaries": cards,
    }


def build_adoption_view(market: MarketInput) -> dict:
    """Return per-change and per-intermediary circular operationalization status."""
    postures = {item.id: item for item in _all_postures(market)}
    intermediary_rows = [
        {
            "intermediary_id": str(item.id),
            "name": item.name,
            "seeded": item.seeded,
            "operationalized": item.adopted,
            "tracked_changes": item.adoption_total,
            "adoption_percentage": _percentage(item.adopted, item.adoption_total),
        }
        for item in sorted(postures.values(), key=lambda item: item.name)
    ]
    change_rows = []
    for change in market.changes:
        statuses = [
            {
                "intermediary_id": str(item.id),
                "name": item.name,
                "seeded": item.seeded,
                "operationalized": change.id in item.completed_change_ids,
            }
            for item in sorted(market.intermediaries, key=lambda item: item.name)
        ]
        implemented = sum(1 for row in statuses if row["operationalized"] is True)
        change_rows.append(
            {
                "change_id": str(change.id),
                "gap_key": f"change:{change.id}",
                "reference": change.reference,
                "title": change.title,
                "severity": _severity(change.severity),
                "operationalized_intermediaries": implemented,
                "total_intermediaries": len(statuses),
                "adoption_percentage": _percentage(implemented, len(statuses)),
                "intermediaries": statuses,
            }
        )
    return {
        "as_of": market.as_of.isoformat(),
        "circular": {
            "circular_id": str(market.circular_id),
            "title": market.circular_title,
        },
        "intermediaries": intermediary_rows,
        "changes": change_rows,
    }


def build_gap_view(market: MarketInput, gap_key: str) -> dict | None:
    """Drill into an obligation-coverage or circular-adoption gap without raw detail."""
    postures = {item.id: item for item in _all_postures(market)}
    matches: list[dict] = []
    gap: dict | None = None

    if gap_key.startswith("obligation:"):
        for posture in postures.values():
            posture_gap = next((item for item in posture.gaps if item["gap_key"] == gap_key), None)
            if posture_gap is None:
                continue
            gap = {
                "gap_key": gap_key,
                "kind": "obligation_coverage",
                "obligation_id": posture_gap["obligation_id"],
                "severity": posture_gap["severity"],
            }
            row = posture.public()
            matches.append(
                {
                    "intermediary_id": row["intermediary_id"],
                    "name": row["name"],
                    "seeded": row["seeded"],
                    "gap_types": posture_gap["gap_types"],
                    "coverage_percentage": row["coverage"]["percentage"],
                    "open_gaps": row["open_gaps"]["total"],
                    "latest_circular_adoption_percentage": row["latest_circular_adoption"][
                        "percentage"
                    ],
                }
            )
    elif gap_key.startswith("change:"):
        change = next((item for item in market.changes if f"change:{item.id}" == gap_key), None)
        if change is not None:
            gap = {
                "gap_key": gap_key,
                "kind": "circular_adoption",
                "change_id": str(change.id),
                "reference": change.reference,
                "title": change.title,
                "severity": _severity(change.severity),
            }
            for item in market.intermediaries:
                if change.id in item.completed_change_ids:
                    continue
                public_posture = postures[item.id].public()
                matches.append(
                    {
                        "intermediary_id": str(item.id),
                        "name": item.name,
                        "seeded": item.seeded,
                        "gap_types": ["not_operationalized"],
                        "coverage_percentage": public_posture["coverage"]["percentage"],
                        "open_gaps": public_posture["open_gaps"]["total"],
                        "latest_circular_adoption_percentage": public_posture[
                            "latest_circular_adoption"
                        ]["percentage"],
                    }
                )

    if gap is None:
        return None
    matches.sort(key=lambda item: (item["coverage_percentage"], item["name"]))
    return {
        "as_of": market.as_of.isoformat(),
        "gap": gap,
        "affected_intermediaries": len(matches),
        "total_intermediaries": len(market.intermediaries),
        "intermediaries": matches,
    }
