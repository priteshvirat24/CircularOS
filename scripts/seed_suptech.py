#!/usr/bin/env python3
"""Seed the Phase-5 supervisory population, deterministically and idempotently.

HONESTY AUDIT TRAIL
===================
REAL:
* Tenant A is an already-existing stock-broker organization. Its applicable population is the
  real, stored active August-2024 stockbroker registry, including
  its real verification verdicts. This script does not create or improve Tenant A controls,
  evidence, gaps, or adoption state.
* The latest-circular targets come from the latest completed real Aug-2024 -> Jun-2025 diff run.
  Only material CREATED/MODIFIED rows are tracked; in the demo database those are the real
  section changes at §17, §71, §72, and §88. The LOW §31 -> §32 terminology cleanup is excluded.

SEEDED (always surfaced as ``seeded: true`` by the API):
* Tenant B references the same real active registry. It receives a deliberately seeded
  well-implemented posture and all four latest-circular changes operationalized.
* Tenant C references the same real registry. It receives a deliberately seeded laggard posture
  with only one of the four latest-circular changes operationalized.
* Seed evidence files are metadata-only markers; no fabricated regulatory document or second
  corpus is created. Phase 7 replaces B/C with onboarded intermediaries without aggregation-code
  changes.

The script only inserts missing seed-keyed rows and updates SupTech organization metadata. A
second run produces no duplicate organizations, users, memberships, controls, mappings,
evidence artifacts, or tasks.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.config import get_settings
from apps.api.services import hash_password
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
    EvidenceStatus,
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

SUPERVISOR_SLUG = "sebi-supervisory-mirror"
SUPERVISOR_EMAIL = "supervisory.viewer@circularos.local"
TENANT_B_SLUG = "suptech-tenant-b-seeded"
TENANT_C_SLUG = "suptech-tenant-c-seeded"


@dataclass(frozen=True)
class SeedReport:
    real_tenant_id: uuid.UUID
    registry_document_id: uuid.UUID
    registry_obligations: int
    circular_id: uuid.UUID
    tracked_changes: int
    created: dict[str, int]


def _increment(created: dict[str, int], key: str) -> None:
    created[key] = created.get(key, 0) + 1


async def _resolve_real_tenant(db: AsyncSession, explicit_id: uuid.UUID | None) -> Organization:
    if explicit_id is not None:
        tenant = await db.get(Organization, explicit_id)
        if tenant is None:
            raise RuntimeError(f"Real tenant {explicit_id} was not found")
        return tenant

    configured = (
        (
            await db.execute(
                select(Organization)
                .where(
                    Organization.entity_type == OrganizationType.STOCK_BROKER.value,
                    Organization.is_active.is_(True),
                    Organization.is_deleted.is_(False),
                )
                .order_by(Organization.created_at, Organization.id)
            )
        )
        .scalars()
        .all()
    )
    real = [
        item
        for item in configured
        if (item.settings or {}).get("suptech", {}).get("seeded") is not True
    ]
    if len(real) != 1:
        raise RuntimeError(
            "Expected exactly one unseeded active stock-broker organization; pass --real-org-id"
        )
    return real[0]


async def _resolve_registry(
    db: AsyncSession,
    explicit_id: uuid.UUID | None,
    expected_count: int | None,
) -> tuple[RegulatoryDocument, list[uuid.UUID]]:
    if explicit_id is not None:
        candidates = [explicit_id]
    else:
        rows = (
            await db.execute(
                select(Obligation.document_id, func.count(Obligation.id))
                .where(Obligation.is_deleted.is_(False))
                .group_by(Obligation.document_id)
                .order_by(Obligation.document_id)
            )
        ).all()
        candidates = [
            row.document_id for row in rows if expected_count is None or row.count == expected_count
        ]
    if len(candidates) != 1:
        raise RuntimeError(
            "Could not identify one real registry document; pass --registry-document-id"
        )
    document = await db.get(RegulatoryDocument, candidates[0])
    if document is None:
        raise RuntimeError(f"Registry document {candidates[0]} was not found")
    obligation_ids = list(
        (
            await db.execute(
                select(Obligation.id)
                .where(
                    Obligation.document_id == document.id,
                    Obligation.is_deleted.is_(False),
                )
                .order_by(Obligation.id)
            )
        ).scalars()
    )
    if expected_count is not None and len(obligation_ids) != expected_count:
        raise RuntimeError(
            f"Registry {document.id} has {len(obligation_ids)} obligations; expected {expected_count}"
        )
    return document, obligation_ids


async def _resolve_circular(
    db: AsyncSession, explicit_id: uuid.UUID | None
) -> tuple[RegulatoryDocument, list[tuple[uuid.UUID, str]]]:
    query = select(DiffRun).where(DiffRun.status == DiffRunStatus.COMPLETED)
    if explicit_id is not None:
        query = query.where(DiffRun.new_document_id == explicit_id)
    run = (
        await db.execute(
            query.order_by(
                DiffRun.completed_at.desc().nullslast(), DiffRun.created_at.desc()
            ).limit(1)
        )
    ).scalar_one_or_none()
    if run is None:
        raise RuntimeError("No completed diff run was found for the latest circular")
    document = await db.get(RegulatoryDocument, run.new_document_id)
    if document is None:
        raise RuntimeError(f"Circular {run.new_document_id} was not found")
    rows = (
        await db.execute(
            select(
                RegulatoryChange.id,
                RegulatoryChange.diff_details["new_ref"].astext.label("reference"),
            )
            .where(
                RegulatoryChange.diff_run_id == run.id,
                RegulatoryChange.change_type.in_((ChangeType.CREATED, ChangeType.MODIFIED)),
                RegulatoryChange.materiality.in_((MaterialityLevel.MEDIUM, MaterialityLevel.HIGH)),
            )
            .order_by(RegulatoryChange.created_at, RegulatoryChange.id)
        )
    ).all()
    changes = [(row.id, row.reference or "unreferenced") for row in rows]
    if not changes:
        raise RuntimeError(f"Circular {document.id} has no material CREATED/MODIFIED changes")
    return document, changes


def _suptech_metadata(
    existing: dict | None,
    *,
    seeded: bool,
    registry_id: uuid.UUID,
    circular_id: uuid.UUID,
    profile: str,
    display_name: str,
) -> dict:
    settings = dict(existing or {})
    settings["suptech"] = {
        "population": True,
        "seeded": seeded,
        "registry_document_id": str(registry_id),
        "latest_circular_id": str(circular_id),
        "profile": profile,
        "display_name": display_name,
    }
    return settings


async def _upsert_organization(
    db: AsyncSession,
    created: dict[str, int],
    *,
    slug: str,
    name: str,
    entity_type: str,
) -> Organization:
    organization = (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if organization is None:
        organization = Organization(slug=slug, name=name, entity_type=entity_type)
        db.add(organization)
        await db.flush()
        _increment(created, "organizations")
    return organization


async def _upsert_supervisor_identity(
    db: AsyncSession,
    created: dict[str, int],
    supervisor: Organization,
    password: str,
) -> None:
    user = (
        await db.execute(select(User).where(User.email == SUPERVISOR_EMAIL))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            email=SUPERVISOR_EMAIL,
            hashed_password=hash_password(password),
            full_name="SEBI Supervisory Viewer",
        )
        db.add(user)
        await db.flush()
        _increment(created, "users")
    else:
        # Explicit CLI input is also the safe credential-rotation path for an existing seed.
        user.hashed_password = hash_password(password)
        user.is_active = True
    membership = (
        await db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.organization_id == supervisor.id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        db.add(
            OrganizationMembership(
                user_id=user.id,
                organization_id=supervisor.id,
                role=UserRole.SUPERVISORY_VIEWER,
            )
        )
        _increment(created, "memberships")
    else:
        membership.role = UserRole.SUPERVISORY_VIEWER
        membership.is_active = True


async def _upsert_control(
    db: AsyncSession, created: dict[str, int], organization: Organization
) -> Control:
    seed_key = f"suptech:{organization.slug}:registry-control"
    control = (
        await db.execute(
            select(Control).where(
                Control.organization_id == organization.id,
                Control.name == seed_key,
            )
        )
    ).scalar_one_or_none()
    if control is None:
        control = Control(
            organization_id=organization.id,
            name=seed_key,
            description="Deliberately seeded registry implementation control",
            control_type="suptech_seed",
            status="active",
            metadata_json={"seeded": True, "seed_key": seed_key},
        )
        db.add(control)
        await db.flush()
        _increment(created, "controls")
    return control


async def _upsert_control_mapping(
    db: AsyncSession,
    created: dict[str, int],
    organization: Organization,
    control: Control,
    obligation_id: uuid.UUID,
) -> None:
    mapping = (
        await db.execute(
            select(ObligationControlMapping.id).where(
                ObligationControlMapping.organization_id == organization.id,
                ObligationControlMapping.control_id == control.id,
                ObligationControlMapping.obligation_id == obligation_id,
            )
        )
    ).scalar_one_or_none()
    if mapping is None:
        db.add(
            ObligationControlMapping(
                organization_id=organization.id,
                control_id=control.id,
                obligation_id=obligation_id,
                mapping_type="implements",
                source="seeded",
                status="active",
            )
        )
        _increment(created, "control_mappings")


async def _upsert_evidence(
    db: AsyncSession,
    created: dict[str, int],
    organization: Organization,
    obligation_id: uuid.UUID,
    evidence_status: EvidenceStatus,
) -> None:
    seed_key = f"suptech:{organization.slug}:{obligation_id}:{evidence_status.value}"
    digest = hashlib.sha256(seed_key.encode()).hexdigest()
    artifact = (
        await db.execute(
            select(EvidenceArtifact).where(
                EvidenceArtifact.organization_id == organization.id,
                EvidenceArtifact.sha256_hash == digest,
            )
        )
    ).scalar_one_or_none()
    if artifact is None:
        artifact = EvidenceArtifact(
            organization_id=organization.id,
            obligation_id=obligation_id,
            file_name=f"{seed_key}.seed",
            file_path=f"seeded://{digest}",
            sha256_hash=digest,
            evidence_type="suptech_seed",
            description="Deliberately seeded evidence-state marker; not a real uploaded artifact",
            status=evidence_status,
            freshness_state=evidence_status.value,
            verification_state="seeded",
            valid_until=date(2099, 12, 31)
            if evidence_status == EvidenceStatus.VALID
            else date(2020, 1, 1),
        )
        db.add(artifact)
        await db.flush()
        _increment(created, "evidence_artifacts")
    mapping = (
        await db.execute(
            select(ObligationEvidenceMapping.id).where(
                ObligationEvidenceMapping.organization_id == organization.id,
                ObligationEvidenceMapping.obligation_id == obligation_id,
                ObligationEvidenceMapping.evidence_artifact_id == artifact.id,
            )
        )
    ).scalar_one_or_none()
    if mapping is None:
        db.add(
            ObligationEvidenceMapping(
                organization_id=organization.id,
                obligation_id=obligation_id,
                evidence_artifact_id=artifact.id,
                source="seeded",
                status="active",
            )
        )
        _increment(created, "evidence_mappings")


async def _upsert_adoption_task(
    db: AsyncSession,
    created: dict[str, int],
    organization: Organization,
    change_id: uuid.UUID,
    reference: str,
    task_status: TaskStatus,
) -> None:
    title = f"SupTech seeded adoption {reference} [{change_id}]"
    task = (
        await db.execute(
            select(ComplianceTask).where(
                ComplianceTask.organization_id == organization.id,
                ComplianceTask.change_id == change_id,
                ComplianceTask.title == title,
                ComplianceTask.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if task is None:
        db.add(
            ComplianceTask(
                organization_id=organization.id,
                change_id=change_id,
                title=title,
                description="Deliberately seeded latest-circular adoption state",
                task_type="suptech_seed",
                status=task_status,
                priority="high",
            )
        )
        _increment(created, "adoption_tasks")
    else:
        task.status = task_status


async def seed_suptech(
    db: AsyncSession,
    *,
    supervisor_password: str,
    real_org_id: uuid.UUID | None = None,
    registry_document_id: uuid.UUID | None = None,
    circular_id: uuid.UUID | None = None,
    expected_registry_count: int | None = None,
) -> SeedReport:
    """Create or reconcile the labelled three-intermediary supervisory population."""
    if len(supervisor_password) < 12:
        raise ValueError("Supervisor password must contain at least 12 characters")
    created: dict[str, int] = {}
    real = await _resolve_real_tenant(db, real_org_id)
    registry, obligation_ids = await _resolve_registry(
        db, registry_document_id, expected_registry_count
    )
    circular, changes = await _resolve_circular(db, circular_id)

    supervisor = await _upsert_organization(
        db,
        created,
        slug=SUPERVISOR_SLUG,
        name="SEBI Supervisory Mirror",
        entity_type=OrganizationType.SUPERVISOR.value,
    )
    await _upsert_supervisor_identity(db, created, supervisor, supervisor_password)
    tenant_b = await _upsert_organization(
        db,
        created,
        slug=TENANT_B_SLUG,
        name="Tenant B — Well Implemented (Seeded)",
        entity_type=OrganizationType.STOCK_BROKER.value,
    )
    tenant_c = await _upsert_organization(
        db,
        created,
        slug=TENANT_C_SLUG,
        name="Tenant C — Laggard (Seeded)",
        entity_type=OrganizationType.STOCK_BROKER.value,
    )

    real.settings = _suptech_metadata(
        real.settings,
        seeded=False,
        registry_id=registry.id,
        circular_id=circular.id,
        profile="real_pipeline_state",
        display_name="Tenant A — Real Registry",
    )
    tenant_b.settings = _suptech_metadata(
        tenant_b.settings,
        seeded=True,
        registry_id=registry.id,
        circular_id=circular.id,
        profile="well_implemented_seed",
        display_name="Tenant B — Well Implemented (Seeded)",
    )
    tenant_c.settings = _suptech_metadata(
        tenant_c.settings,
        seeded=True,
        registry_id=registry.id,
        circular_id=circular.id,
        profile="laggard_seed",
        display_name="Tenant C — Laggard (Seeded)",
    )

    n = len(obligation_ids)
    for organization, control_count, valid_count, stale_count in (
        (
            tenant_b,
            min(int(n * 0.75), n),
            min(int(n * 0.67), n),
            min(int(n * 0.05), max(0, n - int(n * 0.67))),
        ),
        (
            tenant_c,
            min(int(n * 0.35), n),
            min(int(n * 0.12), n),
            min(int(n * 0.15), max(0, n - int(n * 0.12))),
        ),
    ):
        control = await _upsert_control(db, created, organization)
        for obligation_id in obligation_ids[:control_count]:
            await _upsert_control_mapping(db, created, organization, control, obligation_id)
        for obligation_id in obligation_ids[:valid_count]:
            await _upsert_evidence(db, created, organization, obligation_id, EvidenceStatus.VALID)
        for obligation_id in obligation_ids[valid_count : valid_count + stale_count]:
            await _upsert_evidence(db, created, organization, obligation_id, EvidenceStatus.STALE)

    for index, (change_id, reference) in enumerate(changes):
        await _upsert_adoption_task(
            db, created, tenant_b, change_id, reference, TaskStatus.COMPLETED
        )
        await _upsert_adoption_task(
            db,
            created,
            tenant_c,
            change_id,
            reference,
            TaskStatus.COMPLETED if index == 0 else TaskStatus.BLOCKED,
        )

    await db.flush()
    return SeedReport(
        real_tenant_id=real.id,
        registry_document_id=registry.id,
        registry_obligations=len(obligation_ids),
        circular_id=circular.id,
        tracked_changes=len(changes),
        created=created,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supervisor-password", required=True)
    parser.add_argument("--test-db", action="store_true")
    parser.add_argument("--real-org-id", type=uuid.UUID)
    parser.add_argument("--registry-document-id", type=uuid.UUID)
    parser.add_argument("--circular-id", type=uuid.UUID)
    parser.add_argument("--expected-registry-count", type=int, default=None)
    return parser.parse_args()


async def _main(args: argparse.Namespace) -> None:
    settings = get_settings()
    url = settings.test_database_url if args.test_db else settings.database_url
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            report = await seed_suptech(
                db,
                supervisor_password=args.supervisor_password,
                real_org_id=args.real_org_id,
                registry_document_id=args.registry_document_id,
                circular_id=args.circular_id,
                expected_registry_count=args.expected_registry_count,
            )
            await db.commit()
        print(
            "SupTech seed complete: "
            f"real_tenant={report.real_tenant_id} "
            f"registry={report.registry_document_id} "
            f"obligations={report.registry_obligations} "
            f"circular={report.circular_id} "
            f"tracked_changes={report.tracked_changes} "
            f"created={report.created}"
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main(_parse_args()))
