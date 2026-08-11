#!/usr/bin/env python3
"""Build Tenant A's deterministic control, evidence-reference, and adoption layer.

HONESTY LEDGER
==============
REAL INPUTS AND RELATIONSHIPS
* Tenant A is the unseeded stock-broker organization already bound by Phase 5 to the real active
  August-2024 registry.
* Every control mapping is produced by the ordered, inspectable text rules in ``CONTROL_CATALOG``
  over the real obligation actor/action/object/normalized text. No obligation ID is typed into a
  rule and no model proposes a mapping.
* Evidence freshness is derived from ``collection_date + frequency_days`` at an explicit
  ``as_of`` date. The persisted VALID/STALE status is the result of that calculation, never an
  independently selected verdict.
* Latest-circular adoption is derived from the real material RegulatoryChange rows and active
  control topics. The existing system-audit control operationalizes §17; no control topic matches
  §71, §72, or §88, so those remain blocked.

CONSTRUCTED-BUT-PLAUSIBLE INPUTS (NOT CLAIMED AS UPLOADED BROKER RECORDS)
* The 15-control catalogue, owner roles, frequencies, and descriptions represent a realistic
  broker compliance library. In production they are replaced by the intermediary's own library.
* Evidence rows are explicit ``reference://`` records naming plausible registers/reports. They
  do not claim that a file exists, contain no fabricated file content, and carry
  ``constructed_plausible: true`` provenance.
* Catalogue evidence ages create a defensible in-progress mix: most references are within their
  recurrence window, the account-governance register is stale, and the registration dossier
  control is mapped but has no evidence reference yet.

The build is idempotent: controls and evidence are keyed by stable catalogue keys, mappings by
their real foreign keys, and adoption tasks by organization/change. Re-running updates computed
dates/statuses but inserts no duplicate rows.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.config import get_settings
from packages.regulatory_core.models.auth import Organization, OrganizationType
from packages.regulatory_core.models.compliance import (
    ComplianceTask,
    Control,
    EvidenceArtifact,
    EvidenceStatus,
    ObligationControlMapping,
    ObligationEvidenceMapping,
    TaskStatus,
)
from packages.regulatory_core.models.obligations import (
    ChangeType,
    DiffRun,
    DiffRunStatus,
    MaterialityLevel,
    Obligation,
    RegulatoryChange,
)

CONTROL_SOURCE = "tenant_a_rule_v1"
CONTROL_TYPE = "tenant_a_constructed_control"
EVIDENCE_TYPE = "tenant_a_reference"
ADOPTION_TASK_TYPE = "tenant_a_control_adoption"


@dataclass(frozen=True)
class ControlSpec:
    key: str
    name: str
    description: str
    owner_role: str
    frequency: str
    frequency_days: int
    match_any: tuple[str, ...]
    evidence_reference: str
    evidence_age_cycles: float | None = 0.25


@dataclass(frozen=True)
class ObligationFact:
    id: uuid.UUID
    actor: str
    action: str
    object: str
    normalized_obligation: str

    @property
    def search_text(self) -> str:
        return " ".join(
            (self.actor, self.action, self.object, self.normalized_obligation)
        ).casefold()


@dataclass(frozen=True)
class MappingPlan:
    obligation_id: uuid.UUID
    control_key: str
    matched_term: str


@dataclass(frozen=True)
class FreshnessVerdict:
    collection_date: date
    valid_until: date
    status: EvidenceStatus


@dataclass(frozen=True)
class BuildReport:
    tenant_id: uuid.UUID
    registry_id: uuid.UUID
    obligations: int
    catalogue_controls: int
    mapped_obligations: int
    unmapped_obligation_ids: tuple[uuid.UUID, ...]
    evidence_valid: int
    evidence_stale: int
    evidence_missing: int
    adopted_references: tuple[str, ...]
    blocked_references: tuple[str, ...]
    created: dict[str, int]


CONTROL_CATALOG: tuple[ControlSpec, ...] = (
    ControlSpec(
        "fit_proper_screening",
        "Fit-and-proper antecedent screening",
        "Screens membership applicants and retains the antecedent review decision before admission.",
        "Head — Membership Compliance",
        "on occurrence",
        365,
        ("verify antecedents", "know your client", "kyc", "client identity", "due diligence"),
        "Fit-and-Proper Screening Register FY2026",
    ),
    ControlSpec(
        "integrity_declarations",
        "Applicant integrity declaration review",
        "Validates fraud and dishonesty declarations before regulatory registration forwarding.",
        "Compliance Officer",
        "annual",
        365,
        (
            "not been convicted of any offence involving fraud or dishonesty",
            "fraud",
            "dishonesty",
            "convicted",
            "integrity",
            "fit and proper",
        ),
        "Member Integrity Declaration Pack FY2026",
    ),
    ControlSpec(
        "registration_dossier",
        "Regulatory registration dossier approval",
        "Checks prescribed forms, fee evidence, and annexures before a registration filing is released.",
        "Regulatory Filings Manager",
        "on occurrence",
        365,
        (
            "prescribed form along with applicable fees",
            "registration fee",
            "apply for registration",
            "sebi registration",
            "grant of registration",
        ),
        "Stock-Broker Registration Dossier Register",
        None,
    ),
    ControlSpec(
        "records_retention",
        "Registration-record retention and retrieval",
        "Indexes hard-copy registration records and tests retrieval readiness for a regulator request.",
        "Records Management Officer",
        "annual",
        365,
        (
            "preserve hard copies of registration applications",
            "maintain record",
            "record keeping",
            "preserve",
            "log report",
            "books of account",
            "contract note",
            "ecn",
        ),
        "Registration Records Retrieval Test FY2026",
    ),
    ControlSpec(
        "change_in_control",
        "Change-in-control regulatory approval gate",
        "Blocks a control transaction until prior approval and fresh-registration requirements are cleared.",
        "Company Secretary",
        "on occurrence",
        365,
        ("change in control", "amalgam"),
        "Change-in-Control Approval Register FY2026",
    ),
    ControlSpec(
        "registration_surrender",
        "Registration surrender closure checklist",
        "Tracks certificate surrender when a transferor ceases or completes a business transfer.",
        "Company Secretary",
        "on occurrence",
        365,
        ("surrender the certificate of registration", "surrender", "cessation of business"),
        "Registration Surrender Checklist Register",
    ),
    ControlSpec(
        "pan_change_reporting",
        "KMP and dealer PAN change reporting",
        "Reconciles director, KMP, and dealer PAN changes and reports them to the exchange.",
        "HR Compliance Manager",
        "quarterly",
        92,
        ("provide pan details", "pan details", "permanent account number"),
        "KMP and Dealer PAN Reconciliation Q1 FY2026-27",
    ),
    ControlSpec(
        "account_nomenclature",
        "Quarterly bank and demat account nomenclature reconciliation",
        "Reconciles account purpose, opening, and closure notifications against exchange records.",
        "Client Asset Operations Head",
        "quarterly",
        92,
        (
            "appropriate nomenclature",
            "settlement account",
            "all new bank and demat accounts",
            "closure of any reported bank and demat accounts",
            "bank account",
            "client account",
        ),
        "Bank and Demat Account Master Reconciliation Q4 FY2025-26",
        1.5,
    ),
    ControlSpec(
        "client_fund_movements",
        "Daily client-fund nodal account routing",
        "Validates receipts and payouts through the prescribed upstream and downstream nodal accounts.",
        "Treasury Operations Head",
        "daily",
        1,
        (
            "receive clients' funds",
            "make payment to clients",
            "client fund",
            "nodal",
            "running account",
            "margin",
            "collateral",
            "pledge",
            "settlement",
        ),
        "Client Nodal Account Routing Exception Report",
    ),
    ControlSpec(
        "demat_governance",
        "Monthly demat account classification review",
        "Checks permitted demat categories and exchange notification of new or existing accounts.",
        "Depository Operations Head",
        "monthly",
        31,
        (
            "maintain demat accounts only",
            "inform the stock exchanges of existing and new demat",
            "demat",
            "depository participant",
        ),
        "Demat Account Classification Register — July 2026",
    ),
    ControlSpec(
        "client_fund_monitoring",
        "Daily client-fund misuse surveillance",
        "Monitors client-fund balances and investigates G-principle misuse alerts.",
        "Chief Risk Officer",
        "daily",
        1,
        (
            "mechanism for monitoring clients' funds",
            "mechanism to monitor clients' funds",
            "monitor",
            "surveillance",
            "misuse",
            "net worth",
        ),
        "Client-Fund G-Principle Surveillance Log",
    ),
    ControlSpec(
        "alert_response",
        "Client-fund alert investigation and recordkeeping",
        "Records clarifications, inspections, and remediation actions for generated misuse alerts.",
        "Head — Surveillance Investigations",
        "monthly",
        31,
        (
            "seek clarifications, carry out inspections",
            "inspection",
            "investigation",
            "grievance",
            "disciplinary",
            "penalty",
            "complaint",
            "dispute",
            "arbitration",
            "redressal",
        ),
        "Client-Fund Alert Investigation Register — July 2026",
    ),
    ControlSpec(
        "internal_audit_reporting",
        "Half-yearly internal-audit reporting control",
        "Obtains auditor declarations and tracks audit-report submission within the two-month window.",
        "Head — Internal Audit",
        "half-yearly",
        183,
        ("declaration and auditor details", "internal audit reports are submitted", "audit report"),
        "Internal Audit Submission Pack H1 FY2026-27",
    ),
    ControlSpec(
        "exchange_information",
        "Exchange information submission SLA",
        "Tracks requested information through approval and submission within the exchange deadline.",
        "Regulatory Reporting Manager",
        "monthly",
        31,
        (
            "submit required information to stock exchange",
            "submit the required information to the stock exchanges",
            "submit",
            "compliance",
            "inform the exchange",
            "report",
            "inform",
            "notify",
            "disclose",
            "circular",
            "communicate",
        ),
        "Exchange Information Submission Register — July 2026",
    ),
    ControlSpec(
        "internal_audit_execution",
        "Half-yearly internal audit and auditor independence",
        "Schedules the broker audit and enforces auditor tenure and cooling-off requirements.",
        "Audit Committee Secretary",
        "half-yearly",
        183,
        (
            "undergo a half-yearly internal audit",
            "appoint or re-appoint",
            "internal audit",
            "system audit",
            "outsourc",
            "security",
            "cyber",
            "vapt",
            "vulnerability",
            "password",
            "incident",
            "encrypt",
            "algorithm",
            "algo",
            "risk management",
            "policy",
            "procedure",
            "trading system",
        ),
        "Internal Audit Plan and Independence Register H1 FY2026-27",
    ),
)


def plan_mappings(obligations: tuple[ObligationFact, ...]) -> tuple[MappingPlan, ...]:
    """Assign each obligation to the first matching catalogue control."""
    plans: list[MappingPlan] = []
    for obligation in obligations:
        for control in CONTROL_CATALOG:
            matched = next(
                (term for term in control.match_any if term in obligation.search_text), None
            )
            if matched is not None:
                plans.append(MappingPlan(obligation.id, control.key, matched))
                break
    return tuple(plans)


def calculate_freshness(
    collection_date: date, frequency_days: int, as_of: date
) -> FreshnessVerdict:
    """Compute evidence validity from its collection date and recurrence window."""
    if frequency_days <= 0:
        raise ValueError("frequency_days must be positive")
    if collection_date > as_of:
        raise ValueError("collection_date cannot be after as_of")
    valid_until = collection_date + timedelta(days=frequency_days)
    evidence_status = EvidenceStatus.VALID if valid_until >= as_of else EvidenceStatus.STALE
    return FreshnessVerdict(collection_date, valid_until, evidence_status)


def plan_control_freshness(control: ControlSpec, as_of: date) -> FreshnessVerdict | None:
    """Turn catalogue evidence age into dates, then let ``calculate_freshness`` decide status."""
    if control.evidence_age_cycles is None:
        return None
    age_days = max(1, round(control.frequency_days * control.evidence_age_cycles))
    return calculate_freshness(as_of - timedelta(days=age_days), control.frequency_days, as_of)


def _increment(created: dict[str, int], key: str) -> None:
    created[key] = created.get(key, 0) + 1


def _as_fact(obligation: Obligation) -> ObligationFact:
    return ObligationFact(
        id=obligation.id,
        actor=obligation.actor or "",
        action=obligation.action or "",
        object=obligation.object or "",
        normalized_obligation=obligation.normalized_obligation or "",
    )


async def _resolve_tenant(
    db: AsyncSession, explicit_id: uuid.UUID | None
) -> tuple[Organization, uuid.UUID, uuid.UUID]:
    if explicit_id is not None:
        organizations = [await db.get(Organization, explicit_id)]
    else:
        organizations = list(
            (
                await db.execute(
                    select(Organization).where(
                        Organization.entity_type == OrganizationType.STOCK_BROKER.value,
                        Organization.is_active.is_(True),
                        Organization.is_deleted.is_(False),
                    )
                )
            ).scalars()
        )
    real = []
    for organization in organizations:
        if organization is None:
            continue
        settings = (organization.settings or {}).get("suptech", {})
        if settings.get("population") is True and settings.get("seeded") is not True:
            real.append((organization, settings))
    if len(real) != 1:
        raise RuntimeError("Expected exactly one unseeded SupTech stock-broker tenant")
    organization, settings = real[0]
    try:
        registry_id = uuid.UUID(str(settings["registry_document_id"]))
        circular_id = uuid.UUID(str(settings["latest_circular_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Tenant A has invalid SupTech document bindings") from exc
    return organization, registry_id, circular_id


async def _upsert_controls(
    db: AsyncSession, organization: Organization, created: dict[str, int]
) -> dict[str, Control]:
    existing = list(
        (
            await db.execute(select(Control).where(Control.organization_id == organization.id))
        ).scalars()
    )
    by_key = {
        str((control.metadata_json or {}).get("tenant_a_control_key")): control
        for control in existing
        if (control.metadata_json or {}).get("tenant_a_control_key")
    }
    result: dict[str, Control] = {}
    for spec in CONTROL_CATALOG:
        control = by_key.get(spec.key)
        metadata = {
            "tenant_a_control_key": spec.key,
            "constructed_plausible": True,
            "owner_role": spec.owner_role,
            "frequency": spec.frequency,
            "frequency_days": spec.frequency_days,
            "mapping_rule": {"first_match_any": list(spec.match_any), "version": CONTROL_SOURCE},
        }
        if control is None:
            control = Control(
                organization_id=organization.id,
                name=spec.name,
                description=spec.description,
                control_type=CONTROL_TYPE,
                department=spec.owner_role,
                status="active",
                effectiveness="designed_and_operating",
                metadata_json=metadata,
            )
            db.add(control)
            await db.flush()
            _increment(created, "controls")
        else:
            control.name = spec.name
            control.description = spec.description
            control.department = spec.owner_role
            control.status = "active"
            control.effectiveness = "designed_and_operating"
            control.metadata_json = metadata
        result[spec.key] = control
    return result


async def _upsert_mappings(
    db: AsyncSession,
    organization: Organization,
    controls: dict[str, Control],
    plans: tuple[MappingPlan, ...],
    created: dict[str, int],
) -> None:
    existing = {
        (row.control_id, row.obligation_id): row
        for row in (
            await db.execute(
                select(ObligationControlMapping).where(
                    ObligationControlMapping.organization_id == organization.id,
                    ObligationControlMapping.source == CONTROL_SOURCE,
                )
            )
        ).scalars()
    }
    desired: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for plan in plans:
        control = controls[plan.control_key]
        key = (control.id, plan.obligation_id)
        desired.add(key)
        mapping = existing.get(key)
        if mapping is None:
            db.add(
                ObligationControlMapping(
                    organization_id=organization.id,
                    control_id=control.id,
                    obligation_id=plan.obligation_id,
                    mapping_type="implements",
                    confidence=1.0,
                    rationale=f"{CONTROL_SOURCE}: matched normalized term {plan.matched_term!r}",
                    source=CONTROL_SOURCE,
                    status="active",
                )
            )
            _increment(created, "control_mappings")
        else:
            mapping.status = "active"
            mapping.confidence = 1.0
            mapping.rationale = f"{CONTROL_SOURCE}: matched normalized term {plan.matched_term!r}"
    for key, mapping in existing.items():
        if key not in desired:
            mapping.status = "inactive"


async def _upsert_evidence(
    db: AsyncSession,
    organization: Organization,
    controls: dict[str, Control],
    plans: tuple[MappingPlan, ...],
    as_of: date,
    created: dict[str, int],
) -> dict[uuid.UUID, EvidenceStatus]:
    plans_by_control: dict[str, list[MappingPlan]] = {}
    for plan in plans:
        plans_by_control.setdefault(plan.control_key, []).append(plan)

    existing_artifacts = list(
        (
            await db.execute(
                select(EvidenceArtifact).where(
                    EvidenceArtifact.organization_id == organization.id,
                    EvidenceArtifact.evidence_type == EVIDENCE_TYPE,
                )
            )
        ).scalars()
    )
    by_key = {
        str((artifact.extracted_facts or {}).get("tenant_a_control_key")): artifact
        for artifact in existing_artifacts
        if (artifact.extracted_facts or {}).get("tenant_a_control_key")
    }
    obligation_statuses: dict[uuid.UUID, EvidenceStatus] = {}
    for spec in CONTROL_CATALOG:
        mapped = plans_by_control.get(spec.key, [])
        if not mapped:
            continue
        freshness = plan_control_freshness(spec, as_of)
        if freshness is None:
            continue
        control = controls[spec.key]
        reference_uri = f"reference://tenant-a/{spec.key}"
        digest = hashlib.sha256(reference_uri.encode()).hexdigest()
        artifact = by_key.get(spec.key)
        facts = {
            "tenant_a_control_key": spec.key,
            "control_id": str(control.id),
            "constructed_plausible": True,
            "reference_only": True,
            "frequency": spec.frequency,
            "frequency_days": spec.frequency_days,
            "freshness_as_of": as_of.isoformat(),
        }
        if artifact is None:
            artifact = EvidenceArtifact(
                organization_id=organization.id,
                file_name=spec.evidence_reference,
                file_path=reference_uri,
                sha256_hash=digest,
                evidence_type=EVIDENCE_TYPE,
                description=(
                    "Constructed-plausible evidence reference only; no uploaded file or file "
                    "content is claimed."
                ),
                status=freshness.status,
                freshness_state=freshness.status.value,
                verification_state="date_rule_verified",
                collection_date=freshness.collection_date,
                valid_from=freshness.collection_date,
                valid_until=freshness.valid_until,
                extracted_facts=facts,
            )
            db.add(artifact)
            await db.flush()
            _increment(created, "evidence_artifacts")
        else:
            artifact.file_name = spec.evidence_reference
            artifact.file_path = reference_uri
            artifact.status = freshness.status
            artifact.freshness_state = freshness.status.value
            artifact.verification_state = "date_rule_verified"
            artifact.collection_date = freshness.collection_date
            artifact.valid_from = freshness.collection_date
            artifact.valid_until = freshness.valid_until
            artifact.extracted_facts = facts

        existing_mappings = {
            row.obligation_id: row
            for row in (
                await db.execute(
                    select(ObligationEvidenceMapping).where(
                        ObligationEvidenceMapping.organization_id == organization.id,
                        ObligationEvidenceMapping.evidence_artifact_id == artifact.id,
                    )
                )
            ).scalars()
        }
        desired_ids = {plan.obligation_id for plan in mapped}
        for plan in mapped:
            mapping = existing_mappings.get(plan.obligation_id)
            if mapping is None:
                db.add(
                    ObligationEvidenceMapping(
                        organization_id=organization.id,
                        obligation_id=plan.obligation_id,
                        evidence_artifact_id=artifact.id,
                        confidence=1.0,
                        rationale=(
                            f"Evidence reference supports control {spec.key}; freshness computed "
                            f"at {as_of.isoformat()}"
                        ),
                        source=CONTROL_SOURCE,
                        status="active",
                    )
                )
                _increment(created, "evidence_mappings")
            else:
                mapping.status = "active"
            obligation_statuses[plan.obligation_id] = freshness.status
        for obligation_id, mapping in existing_mappings.items():
            if obligation_id not in desired_ids:
                mapping.status = "inactive"
    return obligation_statuses


async def _upsert_adoption(
    db: AsyncSession,
    organization: Organization,
    circular_id: uuid.UUID,
    created: dict[str, int],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    run_id = (
        await db.execute(
            select(DiffRun.id)
            .where(
                DiffRun.new_document_id == circular_id,
                DiffRun.status == DiffRunStatus.COMPLETED,
            )
            .order_by(DiffRun.completed_at.desc().nullslast(), DiffRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if run_id is None:
        raise RuntimeError(f"Circular {circular_id} has no completed diff run")
    changes = (
        await db.execute(
            select(
                RegulatoryChange.id,
                RegulatoryChange.diff_details["new_ref"].astext.label("reference"),
                RegulatoryChange.diff_details["obligation"].astext.label("title"),
            )
            .where(
                RegulatoryChange.diff_run_id == run_id,
                RegulatoryChange.change_type.in_((ChangeType.CREATED, ChangeType.MODIFIED)),
                RegulatoryChange.materiality.in_((MaterialityLevel.MEDIUM, MaterialityLevel.HIGH)),
            )
            .order_by(RegulatoryChange.created_at, RegulatoryChange.id)
        )
    ).all()
    all_controls = list(
        (
            await db.execute(
                select(Control).where(
                    Control.organization_id == organization.id,
                    Control.status == "active",
                    Control.is_deleted.is_(False),
                )
            )
        ).scalars()
    )
    control_topics = " ".join(
        f"{control.name} {control.description or ''} "
        f"{(control.metadata_json or {}).get('source_topic', '')}"
        for control in all_controls
    ).casefold()
    adopted: list[str] = []
    blocked: list[str] = []
    for change in changes:
        reference = change.reference or "unreferenced"
        title = (change.title or "").casefold()
        operationalized = "system audit" in title and "system audit" in control_topics.replace(
            "-", " "
        )
        task = (
            await db.execute(
                select(ComplianceTask).where(
                    ComplianceTask.organization_id == organization.id,
                    ComplianceTask.change_id == change.id,
                    ComplianceTask.task_type == ADOPTION_TASK_TYPE,
                    ComplianceTask.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if task is None:
            task = ComplianceTask(
                organization_id=organization.id,
                change_id=change.id,
                title=f"Tenant A latest-circular adoption {reference}",
                task_type=ADOPTION_TASK_TYPE,
                priority="high",
            )
            db.add(task)
            _increment(created, "adoption_tasks")
        task.status = TaskStatus.COMPLETED if operationalized else TaskStatus.BLOCKED
        task.description = (
            "Operationalized: active system-audit control matches the real change topic."
            if operationalized
            else "Open adoption gap: no active Tenant A control matches the real change topic."
        )
        (adopted if operationalized else blocked).append(reference)
    return tuple(adopted), tuple(blocked)


async def build_tenant_a_layer(
    db: AsyncSession,
    *,
    as_of: date,
    tenant_id: uuid.UUID | None = None,
) -> BuildReport:
    """Build/reconcile Tenant A controls, mappings, evidence references, and adoption."""
    organization, registry_id, circular_id = await _resolve_tenant(db, tenant_id)
    obligations = tuple(
        (
            await db.execute(
                select(Obligation)
                .where(
                    Obligation.document_id == registry_id,
                    Obligation.is_deleted.is_(False),
                )
                .order_by(Obligation.id)
            )
        ).scalars()
    )
    facts = tuple(_as_fact(obligation) for obligation in obligations)
    plans = plan_mappings(facts)
    mapped_ids = {plan.obligation_id for plan in plans}
    controls_with_mappings = {plan.control_key for plan in plans}
    missing_catalogue = {spec.key for spec in CONTROL_CATALOG} - controls_with_mappings
    if missing_catalogue:
        raise RuntimeError(
            f"Control catalogue rules matched no obligation for: {sorted(missing_catalogue)}"
        )

    created: dict[str, int] = {}
    controls = await _upsert_controls(db, organization, created)
    await _upsert_mappings(db, organization, controls, plans, created)
    evidence_statuses = await _upsert_evidence(db, organization, controls, plans, as_of, created)
    adopted, blocked = await _upsert_adoption(db, organization, circular_id, created)
    valid = sum(status == EvidenceStatus.VALID for status in evidence_statuses.values())
    stale = sum(status == EvidenceStatus.STALE for status in evidence_statuses.values())
    missing = len(obligations) - valid - stale
    await db.flush()
    return BuildReport(
        tenant_id=organization.id,
        registry_id=registry_id,
        obligations=len(obligations),
        catalogue_controls=len(CONTROL_CATALOG),
        mapped_obligations=len(mapped_ids),
        unmapped_obligation_ids=tuple(
            obligation.id for obligation in obligations if obligation.id not in mapped_ids
        ),
        evidence_valid=valid,
        evidence_stale=stale,
        evidence_missing=missing,
        adopted_references=adopted,
        blocked_references=blocked,
        created=created,
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected ISO date YYYY-MM-DD") from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-db", action="store_true")
    parser.add_argument("--tenant-id", type=uuid.UUID)
    parser.add_argument("--as-of", type=_parse_date, default=datetime.now(UTC).date())
    return parser.parse_args()


async def _main(args: argparse.Namespace) -> None:
    settings = get_settings()
    url = settings.test_database_url if args.test_db else settings.database_url
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            report = await build_tenant_a_layer(db, as_of=args.as_of, tenant_id=args.tenant_id)
            await db.commit()
        print(
            "Tenant A layer complete: "
            f"tenant={report.tenant_id} registry={report.registry_id} "
            f"obligations={report.obligations} controls={report.catalogue_controls} "
            f"mapped={report.mapped_obligations} "
            f"freshness=valid:{report.evidence_valid},stale:{report.evidence_stale},"
            f"missing:{report.evidence_missing} adopted={report.adopted_references} "
            f"blocked={report.blocked_references} created={report.created}"
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main(_parse_args()))
