"""Persist deterministic organization-level blast-radius assessments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select

from apps.api.database import async_session_maker
from packages.policy_engine.changes import MaterialityLevel as PDEMateriality
from packages.policy_engine.impact import (
    ImpactChange,
    OrgGraph,
    OrgNode,
    OrgNodeKind,
    resolve_blast_radius,
)
from packages.regulatory_core.models.auth import AuditEvent, Organization
from packages.regulatory_core.models.compliance import (
    ComplianceCalendarEvent,
    Control,
    EvidenceRequirement,
    ObligationControlMapping,
    Process,
)
from packages.regulatory_core.models.graph import GraphEdge, GraphNode
from packages.regulatory_core.models.obligations import (
    DiffRun,
    ImpactAssessment,
    Obligation,
    RegulatoryChange,
)


@dataclass(frozen=True)
class ImpactRunSummary:
    change_id: str
    assessment_id: str
    controls: int
    processes: int
    evidence: int
    calendar_events: int
    severity: str
    named_paths: tuple[str, ...]


def _next_half_year_report_deadline(as_of: date) -> date:
    """Return the next last-day-of-May/November deadline on or after ``as_of``."""
    candidates = (
        date(as_of.year, 5, 31),
        date(as_of.year, 11, 30),
        date(as_of.year + 1, 5, 31),
    )
    return next(candidate for candidate in candidates if candidate >= as_of)


async def _latest_high_change() -> RegulatoryChange:
    async with async_session_maker() as db:
        latest_run = (
            await db.execute(select(DiffRun).order_by(DiffRun.created_at.desc()).limit(1))
        ).scalar_one()
        changes = (
            await db.execute(
                select(RegulatoryChange)
                .where(RegulatoryChange.diff_run_id == latest_run.id)
                .order_by(RegulatoryChange.created_at, RegulatoryChange.id)
            )
        ).scalars().all()
        return max(
            changes,
            key=lambda change: {
                "none": 0,
                "low": 1,
                "medium": 2,
                "high": 3,
            }.get(change.materiality.value if change.materiality else "none", 0),
        )


async def persist_demo_blast_radius() -> ImpactRunSummary:
    """Seed truthful operational links from the latest real high-materiality change."""
    change = await _latest_high_change()
    topic = str((change.diff_details or {}).get("obligation") or change.description)
    async with async_session_maker() as db:
        organization = (
            await db.execute(select(Organization).order_by(Organization.created_at).limit(1))
        ).scalar_one()
        existing_assessment = (
            await db.execute(
                select(ImpactAssessment).where(
                    ImpactAssessment.change_id == change.id,
                    ImpactAssessment.organization_id == organization.id,
                )
            )
        ).scalar_one_or_none()
        controls = (await db.execute(select(Control))).scalars().all()
        control = next(
            (
                item
                for item in controls
                if (item.metadata_json or {}).get("source_change_id") == str(change.id)
            ),
            None,
        )
        if control is None:
            control = Control(
                organization_id=organization.id,
                name="System-audit monitoring and supervision control",
                description=(
                    "Operational control derived from the real regulatory change topic: " + topic
                ),
                control_type="preventive_and_detective",
                department="Compliance and Technology Risk",
                status="active",
                metadata_json={
                    "source": "phase3_real_change_seed",
                    "source_change_id": str(change.id),
                    "source_topic": topic,
                },
            )
            db.add(control)
            await db.flush()

        processes = (await db.execute(select(Process))).scalars().all()
        process = next(
            (
                item
                for item in processes
                if item.description and str(change.id) in item.description
            ),
            None,
        )
        if process is None:
            process = Process(
                organization_id=organization.id,
                name="Stock-broker system-audit supervision",
                description=f"Process linked to source change {change.id}: {topic}",
                department="Compliance and Technology Risk",
                status="active",
            )
            db.add(process)
            await db.flush()

        audit_obligation = (
            await db.execute(
                select(Obligation)
                .where(
                    Obligation.normalized_obligation.ilike("%internal audit reports%"),
                    Obligation.normalized_obligation.ilike("%within two months%"),
                )
                .order_by(Obligation.created_at.desc())
                .limit(1)
            )
        ).scalar_one()
        control_mapping = (
            await db.execute(
                select(ObligationControlMapping).where(
                    ObligationControlMapping.obligation_id == audit_obligation.id,
                    ObligationControlMapping.control_id == control.id,
                    ObligationControlMapping.organization_id == organization.id,
                )
            )
        ).scalar_one_or_none()
        if control_mapping is None:
            db.add(
                ObligationControlMapping(
                    obligation_id=audit_obligation.id,
                    control_id=control.id,
                    organization_id=organization.id,
                    mapping_type="change_impact",
                    confidence=1.0,
                    rationale=f"System-audit change {change.id} affects the audit-report duty.",
                    source="deterministic",
                    status="active",
                )
            )

        evidence = (
            await db.execute(
                select(EvidenceRequirement).where(
                    EvidenceRequirement.obligation_id == audit_obligation.id,
                    EvidenceRequirement.organization_id == organization.id,
                    EvidenceRequirement.evidence_type == "Internal audit report",
                )
            )
        ).scalar_one_or_none()
        if evidence is None:
            evidence = EvidenceRequirement(
                obligation_id=audit_obligation.id,
                organization_id=organization.id,
                evidence_type="Internal audit report",
                description=audit_obligation.normalized_obligation,
                collection_frequency=audit_obligation.frequency or "half-yearly",
                is_mandatory=True,
                source="mapped",
            )
            db.add(evidence)
            await db.flush()

        report_deadline = _next_half_year_report_deadline(date.today())
        calendar = (
            await db.execute(
                select(ComplianceCalendarEvent).where(
                    ComplianceCalendarEvent.organization_id == organization.id,
                    ComplianceCalendarEvent.obligation_id == audit_obligation.id,
                    ComplianceCalendarEvent.title == "Submit half-yearly internal audit report",
                )
            )
        ).scalar_one_or_none()
        if calendar is None:
            calendar = ComplianceCalendarEvent(
                organization_id=organization.id,
                obligation_id=audit_obligation.id,
                title="Submit half-yearly internal audit report",
                description=(
                    f"Derived from real obligation {audit_obligation.id}: "
                    f"{audit_obligation.deadline_description}"
                ),
                event_type="deadline",
                event_date=report_deadline,
                is_recurring=True,
                recurrence_rule="FREQ=YEARLY;BYMONTH=5,11;BYMONTHDAY=-1",
                responsible_department="Compliance and Technology Risk",
                evidence_status="pending_review",
                implementation_status="planned",
            )
            db.add(calendar)
            await db.flush()

        async def graph_node(kind: OrgNodeKind, entity_id: UUID, label: str) -> GraphNode:
            node = (
                await db.execute(
                    select(GraphNode).where(
                        GraphNode.node_type == kind.value,
                        GraphNode.entity_id == entity_id,
                    )
                )
            ).scalar_one_or_none()
            if node is None:
                node = GraphNode(
                    node_type=kind.value,
                    entity_id=entity_id,
                    label=label,
                    properties={"source": "phase3_deterministic_impact"},
                    organization_id=organization.id,
                )
                db.add(node)
                await db.flush()
            return node

        change_node = await graph_node(OrgNodeKind.CHANGE, change.id, topic)
        control_node = await graph_node(OrgNodeKind.CONTROL, control.id, control.name)
        process_node = await graph_node(OrgNodeKind.PROCESS, process.id, process.name)
        evidence_node = await graph_node(
            OrgNodeKind.EVIDENCE, evidence.id, evidence.evidence_type
        )
        calendar_node = await graph_node(
            OrgNodeKind.CALENDAR, calendar.id, calendar.title
        )

        async def edge(source: GraphNode, target: GraphNode, relationship: str) -> None:
            exists = (
                await db.execute(
                    select(GraphEdge.id).where(
                        GraphEdge.source_node_id == source.id,
                        GraphEdge.target_node_id == target.id,
                        GraphEdge.relationship_type == relationship,
                    )
                )
            ).scalar_one_or_none()
            if exists is None:
                db.add(
                    GraphEdge(
                        source_node_id=source.id,
                        target_node_id=target.id,
                        relationship_type=relationship,
                        properties={"deterministic": True},
                        confidence=1.0,
                    )
                )

        await edge(change_node, control_node, "AFFECTS")
        await edge(control_node, process_node, "OPERATES_THROUGH")
        await edge(process_node, evidence_node, "REQUIRES_EVIDENCE")
        await edge(evidence_node, calendar_node, "DUE_ON")
        await db.flush()

        graph = OrgGraph(
            nodes=(
                OrgNode(str(change.id), OrgNodeKind.CHANGE, change_node.label),
                OrgNode(str(control.id), OrgNodeKind.CONTROL, control_node.label),
                OrgNode(str(process.id), OrgNodeKind.PROCESS, process_node.label),
                OrgNode(str(evidence.id), OrgNodeKind.EVIDENCE, evidence_node.label),
                OrgNode(str(calendar.id), OrgNodeKind.CALENDAR, calendar_node.label),
            ),
            edges=(
                (str(change.id), str(control.id)),
                (str(control.id), str(process.id)),
                (str(process.id), str(evidence.id)),
                (str(evidence.id), str(calendar.id)),
            ),
        )
        severity = PDEMateriality(change.materiality.value if change.materiality else "none")
        impact = resolve_blast_radius(
            ImpactChange(str(change.id), severity, str(change.id)), graph
        )
        assessment = existing_assessment or ImpactAssessment(
            change_id=change.id, organization_id=organization.id
        )
        assessment.affected_entity_types = ["control", "process", "evidence", "calendar"]
        assessment.affected_departments = ["Compliance and Technology Risk"]
        assessment.affected_controls = list(impact.controls)
        assessment.affected_processes = list(impact.processes)
        assessment.affected_evidence = list(impact.evidence_requirements)
        assessment.affected_calendar_events = list(impact.calendar_events)
        assessment.severity = impact.severity.value
        assessment.summary = impact.explanation
        assessment.details = {
            "named_paths": list(impact.named_paths),
            "source_change_topic": topic,
            "source_obligation_id": str(audit_obligation.id),
            "calendar_derivation": (
                "next half-year-end plus the real two-month deadline yields "
                f"{report_deadline.isoformat()}"
            ),
            "algorithm": "cycle-safe deterministic BFS",
            "unlinked_dimensions": [],
        }
        assessment.confidence = 1.0
        assessment.review_status = "pending"
        db.add(assessment)
        await db.flush()
        db.add(
            AuditEvent(
                organization_id=organization.id,
                action="change.impact_assessed",
                resource_type="regulatory_change",
                resource_id=str(change.id),
                details={
                    "assessment_id": str(assessment.id),
                    "named_paths": list(impact.named_paths),
                    "severity": impact.severity.value,
                    "deterministic": True,
                },
            )
        )
        await db.commit()
        return ImpactRunSummary(
            str(change.id),
            str(assessment.id),
            len(impact.controls),
            len(impact.processes),
            len(impact.evidence_requirements),
            len(impact.calendar_events),
            impact.severity.value,
            impact.named_paths,
        )


async def persist_latest_change_impacts() -> tuple[ImpactRunSummary, ...]:
    """Assess every change from the latest diff run; keep absent org links explicitly empty."""
    linked = await persist_demo_blast_radius()
    async with async_session_maker() as db:
        latest_run = (
            await db.execute(select(DiffRun).order_by(DiffRun.created_at.desc()).limit(1))
        ).scalar_one()
        organization = (
            await db.execute(select(Organization).order_by(Organization.created_at).limit(1))
        ).scalar_one()
        changes = (
            await db.execute(
                select(RegulatoryChange)
                .where(RegulatoryChange.diff_run_id == latest_run.id)
                .order_by(RegulatoryChange.created_at, RegulatoryChange.id)
            )
        ).scalars().all()
        summaries = [linked]
        for change in changes:
            if str(change.id) == linked.change_id:
                continue
            existing = (
                await db.execute(
                    select(ImpactAssessment).where(
                        ImpactAssessment.change_id == change.id,
                        ImpactAssessment.organization_id == organization.id,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                summaries.append(
                    ImpactRunSummary(
                        str(change.id),
                        str(existing.id),
                        len(existing.affected_controls or []),
                        len(existing.affected_processes or []),
                        len(existing.affected_evidence or []),
                        len(existing.affected_calendar_events or []),
                        existing.severity or "none",
                        tuple((existing.details or {}).get("named_paths", [])),
                    )
                )
                continue
            topic = str((change.diff_details or {}).get("obligation") or change.description)
            severity = PDEMateriality(
                change.materiality.value if change.materiality else "none"
            )
            impact = resolve_blast_radius(
                ImpactChange(str(change.id), severity, str(change.id)),
                OrgGraph(
                    nodes=(OrgNode(str(change.id), OrgNodeKind.CHANGE, topic),),
                    edges=(),
                ),
            )
            assessment = ImpactAssessment(
                change_id=change.id,
                organization_id=organization.id,
                affected_entity_types=[],
                affected_departments=[],
                affected_controls=[],
                affected_processes=[],
                affected_evidence=[],
                affected_calendar_events=[],
                severity=impact.severity.value,
                summary=impact.explanation,
                details={
                    "named_paths": [],
                    "source_change_topic": topic,
                    "algorithm": "cycle-safe deterministic BFS",
                    "organization_mapping_status": "no persisted operational links",
                },
                confidence=1.0,
                review_status="pending",
            )
            db.add(assessment)
            await db.flush()
            db.add(
                AuditEvent(
                    organization_id=organization.id,
                    action="change.impact_assessed",
                    resource_type="regulatory_change",
                    resource_id=str(change.id),
                    details={
                        "assessment_id": str(assessment.id),
                        "named_paths": [],
                        "severity": impact.severity.value,
                        "deterministic": True,
                        "organization_mapping_status": "unmapped",
                    },
                )
            )
            summaries.append(
                ImpactRunSummary(
                    str(change.id),
                    str(assessment.id),
                    0,
                    0,
                    0,
                    0,
                    impact.severity.value,
                    (),
                )
            )
        await db.commit()
        return tuple(summaries)
