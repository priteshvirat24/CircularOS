"""Evaluation framework models: datasets, runs, results."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base
from packages.regulatory_core.models.base import TimestampMixin, AuditMixin, generate_uuid7


class EvaluationDataset(Base, TimestampMixin, AuditMixin):
    """Gold-standard evaluation dataset for measuring extraction quality."""

    __tablename__ = "evaluation_datasets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dataset_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # obligation_extraction, clause_classification, retrieval, diff
    version: Mapped[int] = mapped_column(Integer, default=1)
    example_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_evalds_type", "dataset_type"),
        Index("ix_evalds_active", "is_active"),
    )


class EvaluationExample(Base, TimestampMixin, AuditMixin):
    """Individual annotated example in an evaluation dataset."""

    __tablename__ = "evaluation_examples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expected_output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id"), nullable=True
    )
    source_clause_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=True
    )
    annotator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    annotator_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_evalex_dataset", "dataset_id"),
    )


class EvaluationRun(Base, TimestampMixin):
    """An evaluation run measuring system performance against a gold dataset."""

    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_datasets.id"), nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    run_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")

    # Configuration
    model_config_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    prompt_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Aggregate metrics
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    precision: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    f1_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mrr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ndcg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Execution
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_examples: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    passed_examples: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    failed_examples: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_evalrun_dataset", "dataset_id"),
        Index("ix_evalrun_status", "status"),
    )


class EvaluationResult(Base, TimestampMixin):
    """Per-example evaluation result."""

    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    example_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_examples.id"), nullable=False
    )
    predicted_output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    scores: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_evalresult_run", "evaluation_run_id"),
        Index("ix_evalresult_example", "example_id"),
    )
