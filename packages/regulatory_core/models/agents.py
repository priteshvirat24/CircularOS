"""Agent execution, model invocation, and prompt management models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer,
    String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base
from packages.regulatory_core.models.base import (
    TimestampMixin, generate_uuid7,
)


class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class ExtractionRun(Base, TimestampMixin):
    """A complete extraction workflow run."""

    __tablename__ = "extraction_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id"), nullable=False
    )
    workflow_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # ingest, extract, diff, full
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus), nullable=False, default=WorkflowStatus.PENDING
    )
    current_stage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Metrics
    total_clauses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_obligations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    approved_obligations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rejected_obligations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    review_pending: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Execution
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Cost tracking
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # LangGraph state
    checkpoint_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        Index("ix_run_org", "organization_id"),
        Index("ix_run_doc", "document_id"),
        Index("ix_run_status", "status"),
        Index("ix_run_type", "workflow_type"),
    )


class AgentRun(Base, TimestampMixin):
    """Individual agent execution within a workflow."""

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    extraction_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extraction_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus), nullable=False, default=AgentStatus.PENDING
    )

    # Input/Output
    input_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Execution
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Model usage
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Validation
    validation_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    validation_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_agent_run_extraction", "extraction_run_id"),
        Index("ix_agent_run_name", "agent_name"),
        Index("ix_agent_run_status", "status"),
    )


class AgentStep(Base, TimestampMixin):
    """Individual step within an agent run (tool calls, decisions)."""

    __tablename__ = "agent_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # tool_call, llm_call, decision, validation
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    input_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_step_agent_run", "agent_run_id"),
        Index("ix_step_type", "step_type"),
    )


class ModelInvocation(Base, TimestampMixin):
    """Record of every LLM model invocation for cost tracking and audit."""

    __tablename__ = "model_invocations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    agent_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True
    )
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Model info
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Prompt
    prompt_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    system_prompt_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Usage
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Response
    response_format: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    was_structured: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_invocation_agent", "agent_run_id"),
        Index("ix_invocation_provider", "provider"),
        Index("ix_invocation_model", "model_name"),
        Index("ix_invocation_task", "task_type"),
    )


class PromptVersion(Base, TimestampMixin):
    """Versioned prompt registry. Prompts are not scattered in source code."""

    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    task: Mapped[str] = mapped_column(String(200), nullable=False)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output_schema: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    model_config_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_prompt_name_version", "name", "version", unique=True),
        Index("ix_prompt_task", "task"),
        Index("ix_prompt_active", "is_active"),
    )


class WorkflowEvent(Base):
    """Real-time workflow event for SSE streaming."""

    __tablename__ = "workflow_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    extraction_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extraction_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_event_run", "extraction_run_id"),
        Index("ix_event_timestamp", "timestamp"),
        Index("ix_event_type", "event_type"),
    )
