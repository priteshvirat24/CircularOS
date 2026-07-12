"""Regulatory document, clause, and document processing models."""

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


class DocumentType(str, enum.Enum):
    MASTER_CIRCULAR = "master_circular"
    CIRCULAR = "circular"
    AMENDMENT = "amendment"
    NOTIFICATION = "notification"
    GUIDELINE = "guideline"
    ORDER = "order"
    PRESS_RELEASE = "press_release"
    CONSULTATION_PAPER = "consultation_paper"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    PARSING = "parsing"
    PARSED = "parsed"
    STRUCTURING = "structuring"
    STRUCTURED = "structured"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    READY = "ready"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ClauseType(str, enum.Enum):
    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    PERMISSION = "permission"
    EXEMPTION = "exemption"
    DEFINITION = "definition"
    DEADLINE = "deadline"
    PENALTY = "penalty"
    REPORTING_REQUIREMENT = "reporting_requirement"
    RECORDKEEPING_REQUIREMENT = "recordkeeping_requirement"
    DISCLOSURE_REQUIREMENT = "disclosure_requirement"
    PROCEDURAL_INSTRUCTION = "procedural_instruction"
    CONTEXTUAL_STATEMENT = "contextual_statement"
    UNKNOWN = "unknown"


class RegulatoryDomain(str, enum.Enum):
    MARKET_INTERMEDIARIES = "market_intermediaries"
    MUTUAL_FUNDS = "mutual_funds"
    CORPORATE_FINANCE = "corporate_finance"
    MARKET_REGULATION = "market_regulation"
    LEGAL_AFFAIRS = "legal_affairs"
    INVESTMENT_MANAGEMENT = "investment_management"
    DEBT_AND_HYBRID = "debt_and_hybrid"
    ALTERNATIVE_INVESTMENT = "alternative_investment"
    OTHER = "other"


class RegulatorySource(Base, TimestampMixin):
    """Configured regulatory document sources."""

    __tablename__ = "regulatory_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    discovery_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    check_interval_hours: Mapped[int] = mapped_column(Integer, default=24)


class RegulatoryDocument(Base, TimestampMixin, SoftDeleteMixin, VersionMixin, AuditMixin):
    """A regulatory document (circular, amendment, etc.)."""

    __tablename__ = "regulatory_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True,
        comment="NULL for globally shared regulatory documents",
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_sources.id"), nullable=True
    )

    # Document identity
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    reference_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType), nullable=False, default=DocumentType.CIRCULAR
    )
    regulatory_domain: Mapped[Optional[RegulatoryDomain]] = mapped_column(
        Enum(RegulatoryDomain), nullable=True
    )

    # Source provenance
    source_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    download_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_headers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # File metadata
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sha256_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Regulatory metadata
    issued_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    issuing_authority: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applicable_to: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    keywords: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)

    # Processing state
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), nullable=False, default=DocumentStatus.PENDING
    )
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsing_quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ocr_applied: Mapped[bool] = mapped_column(Boolean, default=False)

    # Extracted full text
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_extracted: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    pages: Mapped[List["DocumentPage"]] = relationship(
        back_populates="document", lazy="noload", cascade="all, delete-orphan"
    )
    sections: Mapped[List["DocumentSection"]] = relationship(
        back_populates="document", lazy="noload", cascade="all, delete-orphan"
    )
    clauses: Mapped[List["Clause"]] = relationship(
        back_populates="document", lazy="noload", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_doc_org", "organization_id"),
        Index("ix_doc_status", "status"),
        Index("ix_doc_type", "document_type"),
        Index("ix_doc_hash", "sha256_hash"),
        Index("ix_doc_ref", "reference_number"),
        Index("ix_doc_domain", "regulatory_domain"),
    )


class DocumentPage(Base, TimestampMixin):
    """Individual page of a regulatory document."""

    __tablename__ = "document_pages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_tables: Mapped[bool] = mapped_column(Boolean, default=False)
    has_images: Mapped[bool] = mapped_column(Boolean, default=False)
    tables_json: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    document: Mapped["RegulatoryDocument"] = relationship(back_populates="pages")

    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_page_doc_num"),
        Index("ix_page_doc", "document_id"),
    )


class DocumentSection(Base, TimestampMixin):
    """Hierarchical section within a document."""

    __tablename__ = "document_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_section_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_sections.id"), nullable=True
    )
    section_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    document: Mapped["RegulatoryDocument"] = relationship(back_populates="sections")
    children: Mapped[List["DocumentSection"]] = relationship(
        back_populates="parent", lazy="selectin"
    )
    parent: Mapped[Optional["DocumentSection"]] = relationship(
        back_populates="children", remote_side=[id]
    )

    __table_args__ = (
        Index("ix_section_doc", "document_id"),
        Index("ix_section_parent", "parent_section_id"),
    )


class Clause(Base, TimestampMixin, VersionMixin):
    """Individual regulatory clause extracted from a document."""

    __tablename__ = "clauses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_sections.id"), nullable=True
    )
    parent_clause_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=True
    )

    # Identity
    clause_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    clause_type: Mapped[Optional[ClauseType]] = mapped_column(
        Enum(ClauseType), nullable=True
    )
    level: Mapped[int] = mapped_column(Integer, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # Content
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    heading: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Source coordinates
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    char_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    char_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Classification
    classification_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Embedding
    embedding_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    document: Mapped["RegulatoryDocument"] = relationship(back_populates="clauses")
    children: Mapped[List["Clause"]] = relationship(
        back_populates="parent_clause", lazy="selectin"
    )
    parent_clause: Mapped[Optional["Clause"]] = relationship(
        back_populates="children", remote_side=[id]
    )

    __table_args__ = (
        Index("ix_clause_doc", "document_id"),
        Index("ix_clause_section", "section_id"),
        Index("ix_clause_type", "clause_type"),
        Index("ix_clause_parent", "parent_clause_id"),
    )


class DocumentRelationship(Base, TimestampMixin):
    """Relationships between regulatory documents (amends, supersedes, references)."""

    __tablename__ = "document_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id"), nullable=False
    )
    target_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # AMENDS, SUPERSEDES, REFERENCES
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    __table_args__ = (
        Index("ix_docrel_source", "source_document_id"),
        Index("ix_docrel_target", "target_document_id"),
        Index("ix_docrel_type", "relationship_type"),
    )
