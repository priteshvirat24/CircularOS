"""Compliance operations models: controls, evidence, calendar, risk, tasks."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, Integer,
    String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from packages.regulatory_core.models.base import (
    TimestampMixin, SoftDeleteMixin, VersionMixin, AuditMixin, generate_uuid7,
)


class EvidenceStatus(str, enum.Enum):
    MISSING = "missing"
    PENDING_REVIEW = "pending_review"
    VALID = "valid"
    STALE = "stale"
    INSUFFICIENT = "insufficient"
    REJECTED = "rejected"


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class Control(Base, TimestampMixin, SoftDeleteMixin, VersionMixin, AuditMixin):
    """Organizational control that implements compliance with obligations."""

    __tablename__ = "controls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    control_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="active")
    effectiveness: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_assessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_control_org", "organization_id"),
        Index("ix_control_dept", "department"),
        Index("ix_control_status", "status"),
    )


class Process(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Organizational process affected by regulatory obligations."""

    __tablename__ = "processes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="active")

    __table_args__ = (
        Index("ix_process_org", "organization_id"),
    )


class EvidenceRequirement(Base, TimestampMixin, AuditMixin):
    """What evidence is required to demonstrate compliance with an obligation."""

    __tablename__ = "evidence_requirements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=False
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    evidence_type: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    collection_frequency: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    validity_period_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # extracted, manual, mapped

    __table_args__ = (
        Index("ix_evreq_obl", "obligation_id"),
        Index("ix_evreq_org", "organization_id"),
    )


class EvidenceArtifact(Base, TimestampMixin, AuditMixin):
    """Uploaded evidence artifact demonstrating compliance."""

    __tablename__ = "evidence_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    evidence_requirement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_requirements.id"), nullable=True
    )
    obligation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=True
    )

    # File metadata
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Evidence metadata
    evidence_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    collection_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Verification
    status: Mapped[EvidenceStatus] = mapped_column(
        Enum(EvidenceStatus), nullable=False, default=EvidenceStatus.PENDING_REVIEW
    )
    freshness_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    verification_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mapping_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Extracted content
    extracted_facts: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    mapping_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_evidence_org", "organization_id"),
        Index("ix_evidence_obl", "obligation_id"),
        Index("ix_evidence_req", "evidence_requirement_id"),
        Index("ix_evidence_status", "status"),
        Index("ix_evidence_hash", "sha256_hash"),
    )


class EvidenceAuditEntry(Base):
    """Append-only evidence audit trail. Never updated or deleted."""

    __tablename__ = "evidence_audit_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    evidence_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_artifacts.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    previous_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_evaudit_artifact", "evidence_artifact_id"),
        Index("ix_evaudit_timestamp", "timestamp"),
    )


class ObligationControlMapping(Base, TimestampMixin, AuditMixin):
    """Maps obligations to organizational controls."""

    __tablename__ = "obligation_control_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=False
    )
    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("controls.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    mapping_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # ai, manual
    status: Mapped[str] = mapped_column(String(50), default="active")

    __table_args__ = (
        Index("ix_ocm_obl", "obligation_id"),
        Index("ix_ocm_control", "control_id"),
        Index("ix_ocm_org", "organization_id"),
    )


class ObligationEvidenceMapping(Base, TimestampMixin, AuditMixin):
    """Maps obligations to evidence artifacts."""

    __tablename__ = "obligation_evidence_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=False
    )
    evidence_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_artifacts.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")

    __table_args__ = (
        Index("ix_oem_obl", "obligation_id"),
        Index("ix_oem_evidence", "evidence_artifact_id"),
        Index("ix_oem_org", "organization_id"),
    )


class ComplianceTask(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Implementation task generated from obligations."""

    __tablename__ = "compliance_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    obligation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=True
    )
    change_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), nullable=False, default=TaskStatus.TODO
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_task_org", "organization_id"),
        Index("ix_task_status", "status"),
        Index("ix_task_assigned", "assigned_to"),
        Index("ix_task_obl", "obligation_id"),
    )


class ComplianceCalendarEvent(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Calendar event derived from regulatory obligations."""

    __tablename__ = "compliance_calendar_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    obligation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # deadline, recurring, effective_date, evidence_renewal
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    responsible_department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    evidence_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    implementation_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_cal_org", "organization_id"),
        Index("ix_cal_date", "event_date"),
        Index("ix_cal_type", "event_type"),
        Index("ix_cal_obl", "obligation_id"),
    )


class RiskScore(Base, TimestampMixin):
    """Versioned risk score calculation for an obligation."""

    __tablename__ = "risk_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )

    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_category: Mapped[str] = mapped_column(String(20), nullable=False)

    # Factor contributions
    regulatory_severity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    investor_impact: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deadline_proximity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence_freshness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    control_coverage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    change_magnitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    historical_gaps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    validation_uncertainty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Calculation metadata
    factor_weights: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    calculation_formula: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")
    underlying_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_risk_obl", "obligation_id"),
        Index("ix_risk_org", "organization_id"),
        Index("ix_risk_score", "overall_score"),
        Index("ix_risk_category", "risk_category"),
    )
