"""The single authorization and aggregate-only database choke-point for SupTech.

All supervisory queries are methods on an authorized ``SupTechAccess`` instance. SQL selects
only identifiers, status values, dates, names, and public regulatory labels. No selected or
returned shape can carry document/page/clause text, control descriptions, evidence paths, or
mapping rationale.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user_optional
from packages.regulatory_core.models.auth import (
    Organization,
    OrganizationMembership,
    OrganizationType,
    User,
    UserRole,
)
from packages.regulatory_core.models.compliance import (
    ComplianceTask,
    Control,
    EvidenceArtifact,
    ObligationControlMapping,
    ObligationEvidenceMapping,
    TaskStatus,
)
from packages.regulatory_core.models.documents import RegulatoryDocument
from packages.regulatory_core.models.obligations import (
    ChangeType,
    DiffRun,
    DiffRunStatus,
    MaterialityLevel,
    Obligation,
    RegulatoryChange,
)
from packages.suptech.types import (
    ChangeInput,
    EvidenceInput,
    IntermediaryInput,
    MarketInput,
    ObligationInput,
)

_AUTHORIZED = object()
_SUPTECH_SETTINGS_KEY = "suptech"


class SupTechDataError(RuntimeError):
    """Raised when the requested supervisory population is incomplete or ambiguous."""


def deny_supervisory_raw_access(
    user: User | None = Depends(get_current_user_optional),
) -> None:
    """Deny supervisory viewers every non-SupTech data router.

    The viewer role is deliberately narrower than an auditor role: its only data surface is the
    aggregate API guarded below. Anonymous access is permitted only where the endpoint itself
    explicitly exposes a public demo read.
    """
    if user is not None and getattr(user, "_current_role", None) == UserRole.SUPERVISORY_VIEWER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisory viewers may access aggregate SupTech endpoints only",
        )


def _parse_uuid(value: object, field: str, organization_id: uuid.UUID) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise SupTechDataError(
            f"SupTech population organization {organization_id} has invalid {field}"
        ) from exc


def _suptech_settings(raw: dict | None) -> dict:
    value = (raw or {}).get(_SUPTECH_SETTINGS_KEY, {})
    return value if isinstance(value, dict) else {}


class SupTechAccess:
    """Authorized access object that can emit aggregate-only ``MarketInput`` data."""

    def __init__(self, db: AsyncSession, marker: object) -> None:
        if marker is not _AUTHORIZED:
            raise RuntimeError("Use SupTechAccess.authorize()")
        self._db = db

    @classmethod
    async def authorize(cls, db: AsyncSession, user: User) -> SupTechAccess:
        """Verify token context, active DB membership, viewer role, and supervisor org type."""
        if getattr(user, "_current_role", None) != UserRole.SUPERVISORY_VIEWER.value:
            raise HTTPException(status_code=403, detail="Supervisory viewer role required")
        raw_org_id = getattr(user, "_current_org_id", None)
        try:
            organization_id = uuid.UUID(str(raw_org_id))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=403, detail="Supervisor organization required") from exc

        row = (
            await db.execute(
                select(OrganizationMembership.role, Organization.entity_type)
                .join(Organization, Organization.id == OrganizationMembership.organization_id)
                .where(
                    OrganizationMembership.user_id == user.id,
                    OrganizationMembership.organization_id == organization_id,
                    OrganizationMembership.is_active.is_(True),
                    Organization.is_active.is_(True),
                    Organization.is_deleted.is_(False),
                )
            )
        ).one_or_none()
        if row is None or row.role != UserRole.SUPERVISORY_VIEWER:
            raise HTTPException(status_code=403, detail="Active supervisory membership required")
        if row.entity_type != OrganizationType.SUPERVISOR.value:
            raise HTTPException(status_code=403, detail="Supervisor organization required")
        return cls(db, _AUTHORIZED)

    @classmethod
    def demo_read(cls, db: AsyncSession) -> SupTechAccess:
        """Create the aggregate-only demo read context without exposing raw tenant records."""
        return cls(db, _AUTHORIZED)

    async def load_market(self, circular_id: uuid.UUID | None = None) -> MarketInput:
        """Load live supervisory signals, reduced to the safe contract in ``types.py``."""
        population_rows = (
            await self._db.execute(
                select(Organization.id, Organization.name, Organization.settings)
                .where(
                    Organization.is_active.is_(True),
                    Organization.is_deleted.is_(False),
                    Organization.entity_type != OrganizationType.SUPERVISOR.value,
                )
                .order_by(Organization.name, Organization.id)
            )
        ).all()

        population: list[tuple[uuid.UUID, str, bool, uuid.UUID, uuid.UUID]] = []
        for row in population_rows:
            settings = _suptech_settings(row.settings)
            if settings.get("population") is not True:
                continue
            registry_id = _parse_uuid(
                settings.get("registry_document_id"), "registry_document_id", row.id
            )
            latest_id = _parse_uuid(
                settings.get("latest_circular_id"), "latest_circular_id", row.id
            )
            display_name = settings.get("display_name")
            name = (
                display_name.strip()
                if isinstance(display_name, str) and display_name.strip()
                else row.name
            )
            population.append(
                (row.id, name, settings.get("seeded") is True, registry_id, latest_id)
            )

        if not population:
            raise SupTechDataError("No SupTech intermediary population is configured")

        configured_latest = {item[4] for item in population}
        if circular_id is None:
            if len(configured_latest) != 1:
                raise SupTechDataError("SupTech population has inconsistent latest circular IDs")
            circular_id = configured_latest.pop()

        circular = (
            await self._db.execute(
                select(RegulatoryDocument.id, RegulatoryDocument.title).where(
                    RegulatoryDocument.id == circular_id,
                    RegulatoryDocument.is_deleted.is_(False),
                )
            )
        ).one_or_none()
        if circular is None:
            raise SupTechDataError(f"Circular {circular_id} was not found")

        diff_run_id = (
            await self._db.execute(
                select(DiffRun.id)
                .where(
                    DiffRun.new_document_id == circular_id,
                    DiffRun.status == DiffRunStatus.COMPLETED,
                )
                .order_by(DiffRun.completed_at.desc().nullslast(), DiffRun.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if diff_run_id is None:
            raise SupTechDataError(f"Circular {circular_id} has no completed diff run")

        changes = await self._load_changes(diff_run_id)
        org_ids = [item[0] for item in population]
        registry_ids = {item[3] for item in population}
        obligation_rows = (
            await self._db.execute(
                select(Obligation.id, Obligation.document_id, Obligation.risk_level).where(
                    Obligation.document_id.in_(registry_ids),
                    Obligation.is_deleted.is_(False),
                )
            )
        ).all()
        obligations_by_document: dict[uuid.UUID, list[ObligationInput]] = {}
        all_obligation_ids: set[uuid.UUID] = set()
        for row in obligation_rows:
            severity = row.risk_level.value if row.risk_level is not None else "medium"
            item = ObligationInput(id=row.id, severity=severity)
            obligations_by_document.setdefault(row.document_id, []).append(item)
            all_obligation_ids.add(row.id)

        controlled = await self._load_controlled(org_ids, all_obligation_ids)
        evidence = await self._load_evidence(org_ids, all_obligation_ids)
        completed = await self._load_completed_changes(org_ids, {item.id for item in changes})

        intermediaries = []
        for org_id, name, seeded, registry_id, _latest_id in population:
            obligations = tuple(
                sorted(obligations_by_document.get(registry_id, ()), key=lambda item: item.id)
            )
            intermediaries.append(
                IntermediaryInput(
                    id=org_id,
                    name=name,
                    seeded=seeded,
                    obligations=obligations,
                    controlled_obligation_ids=frozenset(controlled.get(org_id, ())),
                    evidence=tuple(evidence.get(org_id, ())),
                    completed_change_ids=frozenset(completed.get(org_id, ())),
                )
            )
        return MarketInput(
            as_of=datetime.now(UTC).date(),
            circular_id=circular.id,
            circular_title=circular.title,
            changes=tuple(changes),
            intermediaries=tuple(intermediaries),
        )

    async def _load_changes(self, diff_run_id: uuid.UUID) -> list[ChangeInput]:
        rows = (
            await self._db.execute(
                select(
                    RegulatoryChange.id,
                    RegulatoryChange.diff_details["new_ref"].astext.label("reference"),
                    RegulatoryChange.diff_details["obligation"].astext.label("title"),
                    RegulatoryChange.materiality,
                )
                .where(
                    RegulatoryChange.diff_run_id == diff_run_id,
                    RegulatoryChange.change_type.in_((ChangeType.CREATED, ChangeType.MODIFIED)),
                    RegulatoryChange.materiality.in_(
                        (MaterialityLevel.MEDIUM, MaterialityLevel.HIGH)
                    ),
                )
                .order_by(RegulatoryChange.created_at, RegulatoryChange.id)
            )
        ).all()
        return [
            ChangeInput(
                id=row.id,
                reference=row.reference or "unreferenced",
                title=row.title or "Regulatory obligation change",
                severity=row.materiality.value.lower(),
            )
            for row in rows
        ]

    async def _load_controlled(
        self, org_ids: list[uuid.UUID], obligation_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, set[uuid.UUID]]:
        if not obligation_ids:
            return {}
        rows = (
            await self._db.execute(
                select(
                    ObligationControlMapping.organization_id, ObligationControlMapping.obligation_id
                )
                .join(Control, Control.id == ObligationControlMapping.control_id)
                .where(
                    ObligationControlMapping.organization_id.in_(org_ids),
                    ObligationControlMapping.obligation_id.in_(obligation_ids),
                    ObligationControlMapping.status == "active",
                    Control.status == "active",
                    Control.is_deleted.is_(False),
                )
            )
        ).all()
        result: dict[uuid.UUID, set[uuid.UUID]] = {}
        for row in rows:
            result.setdefault(row.organization_id, set()).add(row.obligation_id)
        return result

    async def _load_evidence(
        self, org_ids: list[uuid.UUID], obligation_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, list[EvidenceInput]]:
        if not obligation_ids:
            return {}
        rows = (
            await self._db.execute(
                select(
                    ObligationEvidenceMapping.organization_id,
                    ObligationEvidenceMapping.obligation_id,
                    EvidenceArtifact.status,
                    EvidenceArtifact.valid_until,
                )
                .join(
                    EvidenceArtifact,
                    EvidenceArtifact.id == ObligationEvidenceMapping.evidence_artifact_id,
                )
                .where(
                    ObligationEvidenceMapping.organization_id.in_(org_ids),
                    ObligationEvidenceMapping.obligation_id.in_(obligation_ids),
                    ObligationEvidenceMapping.status == "active",
                    EvidenceArtifact.organization_id == ObligationEvidenceMapping.organization_id,
                )
            )
        ).all()
        result: dict[uuid.UUID, list[EvidenceInput]] = {}
        for row in rows:
            result.setdefault(row.organization_id, []).append(
                EvidenceInput(
                    obligation_id=row.obligation_id,
                    status=row.status.value,
                    valid_until=row.valid_until,
                )
            )
        return result

    async def _load_completed_changes(
        self, org_ids: list[uuid.UUID], change_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, set[uuid.UUID]]:
        if not change_ids:
            return {}
        rows = (
            await self._db.execute(
                select(ComplianceTask.organization_id, ComplianceTask.change_id).where(
                    ComplianceTask.organization_id.in_(org_ids),
                    ComplianceTask.change_id.in_(change_ids),
                    ComplianceTask.status == TaskStatus.COMPLETED,
                    ComplianceTask.is_deleted.is_(False),
                )
            )
        ).all()
        result: dict[uuid.UUID, set[uuid.UUID]] = {}
        for row in rows:
            if row.change_id is not None:
                result.setdefault(row.organization_id, set()).add(row.change_id)
        return result
