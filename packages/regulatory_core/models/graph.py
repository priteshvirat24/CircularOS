"""Knowledge graph relational tables (PostgreSQL-based graph implementation).

Uses relational tables with a graph repository abstraction to allow
future migration to Neo4j if needed.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime, Float, ForeignKey, Index, Integer,
    String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base
from packages.regulatory_core.models.base import TimestampMixin, generate_uuid7


class GraphNode(Base, TimestampMixin):
    """Generic graph node representing a regulatory entity."""

    __tablename__ = "graph_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    node_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # Regulation, Circular, Clause, Obligation, Actor, Control, etc.
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, comment="ID of the referenced domain entity"
    )
    label: Mapped[str] = mapped_column(String(1000), nullable=False)
    properties: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_gnode_type", "node_type"),
        Index("ix_gnode_entity", "entity_id"),
        Index("ix_gnode_org", "organization_id"),
        Index("ix_gnode_type_entity", "node_type", "entity_id", unique=True),
    )


class GraphEdge(Base, TimestampMixin):
    """Directed edge between graph nodes."""

    __tablename__ = "graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # AMENDS, SUPERSEDES, CREATES_OBLIGATION, APPLIES_TO, etc.
    properties: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    __table_args__ = (
        Index("ix_gedge_source", "source_node_id"),
        Index("ix_gedge_target", "target_node_id"),
        Index("ix_gedge_type", "relationship_type"),
        Index("ix_gedge_source_type", "source_node_id", "relationship_type"),
        Index("ix_gedge_target_type", "target_node_id", "relationship_type"),
    )


class ClauseEmbedding(Base, TimestampMixin):
    """Vector embedding for a clause, stored alongside pgvector column."""

    __tablename__ = "clause_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid7
    )
    clause_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_documents.id"), nullable=False
    )
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    # The actual vector column is added via raw SQL migration due to
    # pgvector's dynamic dimension requirement
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_cembed_clause", "clause_id"),
        Index("ix_cembed_doc", "document_id"),
        Index("ix_cembed_model", "embedding_model"),
    )
