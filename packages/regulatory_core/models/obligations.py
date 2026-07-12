"""Obligation extraction, validation, and review models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from packages.regulatory_core.models.base import (
    TimestampMixin, SoftDeleteMixin, VersionMixin, AuditMixin, generate_uuid7,
)


class ObligationStatus(str, enum.Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class ReviewAction(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT_AND_APPROVE = "edit_and_approve"
    REQUEST_REPROCESSING = "request_reprocessing"
    ESCALATE = "escalate"


class RiskLevel(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class ChangeType(str, enum.Enum):
    CREATED = "created"
    MODIFIED = "modified"
    REMOVED = "removed"
    SUPERSEDED = "superseded"
    DEADLINE_CHANGED = "deadline_changed"
    APPLICABILITY_CHANGED = "applicability_changed"
    ACTOR_CHANGED = "actor_changed"
    EVIDENCE_REQUIREMENT_CHANGED = "evidence_requirement_changed"
    PENALTY_CHANGED = "penalty_changed"
    EXCEPTION_CHANGED = "exception_changed"


class Obligation(Base, TimestampMixin, SoftDeleteMixin, VersionMixin, AuditMixin):
    """Structured regulatory obligation extracted from a clause."""

    __tablename__ = "obligations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True,
        comment="NULL for global obligations from shared documents",
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id"), nullable=False
    )
    clause_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=False
    )

    # Source text
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_obligation: Mapped[str] = mapped_column(Text, nullable=False)

    # Structured obligation fields
    actor: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    object: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conditions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    exceptions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    applicability: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    frequency: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Dates
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    deadline_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Requirements
    evidence_requirements: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    record_retention_requirement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    penalty_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cross_references: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Organizational mapping
    responsible_department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    affected_controls: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    affected_processes: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Risk assessment
    risk_level: Mapped[Optional[RiskLevel]] = mapped_column(Enum(RiskLevel), nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_factors: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Extraction provenance
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extraction_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    prompt_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Citation coordinates
    citation_coordinates: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Validation & Review
    validation_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    validation_results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[ObligationStatus] = mapped_column(
        Enum(ObligationStatus), nullable=False, default=ObligationStatus.CANDIDATE
    )
    review_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    citations: Mapped[List["ObligationCitation"]] = relationship(
        back_populates="obligation", lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_obl_org", "organization_id"),
        Index("ix_obl_doc", "document_id"),
        Index("ix_obl_clause", "clause_id"),
        Index("ix_obl_status", "status"),
        Index("ix_obl_risk", "risk_level"),
        Index("ix_obl_confidence", "confidence"),
        Index("ix_obl_deadline", "deadline"),
        Index("ix_obl_extraction_run", "extraction_run_id"),
    )


class ObligationCitation(Base, TimestampMixin):
    """Source citation linking obligation fields to exact source spans."""

    __tablename__ = "obligation_citations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    cited_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    char_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    char_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    clause_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=True
    )
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    obligation: Mapped["Obligation"] = relationship(back_populates="citations")

    __table_args__ = (
        Index("ix_citation_obl", "obligation_id"),
        Index("ix_citation_field", "field_name"),
    )


class ValidationResult(Base, TimestampMixin):
    """Deterministic and model-based validation results for extracted obligations."""

    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id", ondelete="CASCADE"), nullable=False
    )
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    validator_name: Mapped[str] = mapped_column(String(100), nullable=False)
    validator_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # deterministic, model_based
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_validation_obl", "obligation_id"),
        Index("ix_validation_run", "extraction_run_id"),
    )


class ReviewTask(Base, TimestampMixin):
    """Human review queue item."""

    __tablename__ = "review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    obligation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=True
    )
    change_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    task_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # obligation_review, change_review, evidence_review
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    context: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_review_org", "organization_id"),
        Index("ix_review_status", "status"),
        Index("ix_review_type", "task_type"),
        Index("ix_review_assigned", "assigned_to"),
    )


class ReviewDecision(Base, TimestampMixin):
    """Immutable record of a review decision."""

    __tablename__ = "review_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    review_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_tasks.id"), nullable=False
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    action: Mapped[ReviewAction] = mapped_column(Enum(ReviewAction), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    edits: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    previous_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_decision_task", "review_task_id"),
        Index("ix_decision_reviewer", "reviewer_id"),
    )


class RegulatoryChange(Base, TimestampMixin, AuditMixin):
    """Detected regulatory change between document versions."""

    __tablename__ = "regulatory_changes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    old_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id"), nullable=True
    )
    new_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id"), nullable=False
    )
    old_clause_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=True
    )
    new_clause_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=True
    )
    old_obligation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=True
    )
    new_obligation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=True
    )

    change_type: Mapped[ChangeType] = mapped_column(Enum(ChangeType), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    old_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diff_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verification_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    review_status: Mapped[str] = mapped_column(String(50), default="pending")
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    __table_args__ = (
        Index("ix_change_old_doc", "old_document_id"),
        Index("ix_change_new_doc", "new_document_id"),
        Index("ix_change_type", "change_type"),
        Index("ix_change_review", "review_status"),
    )


class ImpactAssessment(Base, TimestampMixin):
    """Impact analysis of a regulatory change."""

    __tablename__ = "impact_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    change_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_changes.id"), nullable=False
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    affected_entity_types: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    affected_departments: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    affected_controls: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    affected_processes: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    affected_evidence: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    affected_tasks: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    affected_calendar_events: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_status: Mapped[str] = mapped_column(String(50), default="pending")

    __table_args__ = (
        Index("ix_impact_change", "change_id"),
        Index("ix_impact_org", "organization_id"),
    )
