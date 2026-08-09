"""Aggregate-only data contracts shared by SupTech access and calculation code.

These types intentionally have no fields capable of carrying source document text, control
descriptions, evidence paths, or mapping rationale. The database boundary reduces rows into
this safe shape before the deterministic aggregation layer can see them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ObligationInput:
    id: uuid.UUID
    severity: str


@dataclass(frozen=True)
class EvidenceInput:
    obligation_id: uuid.UUID
    status: str
    valid_until: date | None


@dataclass(frozen=True)
class ChangeInput:
    id: uuid.UUID
    reference: str
    title: str
    severity: str


@dataclass(frozen=True)
class IntermediaryInput:
    id: uuid.UUID
    name: str
    seeded: bool
    obligations: tuple[ObligationInput, ...]
    controlled_obligation_ids: frozenset[uuid.UUID]
    evidence: tuple[EvidenceInput, ...]
    completed_change_ids: frozenset[uuid.UUID]


@dataclass(frozen=True)
class MarketInput:
    as_of: date
    circular_id: uuid.UUID
    circular_title: str
    changes: tuple[ChangeInput, ...]
    intermediaries: tuple[IntermediaryInput, ...]
