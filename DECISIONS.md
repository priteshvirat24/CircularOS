# CircularOS - Architecture Decision Records

## ADR-001: Background Processing - Celery over Temporal

**Status**: Accepted  
**Date**: 2026-07-12  

**Context**: The system requires durable background workflows for document ingestion, agent pipelines, and evaluation runs. Temporal provides superior workflow durability but adds significant operational complexity (Temporal server, Temporal UI, additional database).

**Decision**: Use Celery + Redis with explicit workflow-state persistence and idempotency patterns.

**Consequences**:
- Lower deployment complexity (Redis already needed for caching)
- Must implement explicit checkpointing and idempotency
- Must implement workflow state machine manually
- Can migrate to Temporal later if scale demands it

---

## ADR-002: Knowledge Graph - PostgreSQL Relational Tables over Neo4j

**Status**: Accepted  
**Date**: 2026-07-12  

**Context**: The regulatory knowledge graph requires entity-relationship modeling. Neo4j provides native graph queries but adds another database dependency.

**Decision**: Implement graph as PostgreSQL relational tables with a graph repository abstraction layer. The abstraction allows future migration to Neo4j.

**Consequences**:
- Single database system (PostgreSQL)
- Simpler deployment and backup
- Complex graph traversals may be less efficient
- Repository abstraction preserves migration path

---

## ADR-003: Vector Store - pgvector over Standalone Solutions

**Status**: Accepted  
**Date**: 2026-07-12  

**Context**: The system needs vector similarity search for semantic retrieval. Options include Pinecone, Weaviate, Qdrant, Milvus, ChromaDB, or pgvector.

**Decision**: Use PostgreSQL + pgvector extension.

**Consequences**:
- Single database for relational, vector, and full-text search
- ACID transactions across all data types
- Metadata filtering natively supported via SQL
- May need HNSW indexes for performance at scale

---

## ADR-004: Authentication - JWT with Refresh Tokens

**Status**: Accepted  
**Date**: 2026-07-12  

**Context**: The system needs authentication supporting multi-tenancy and role-based access.

**Decision**: JWT access tokens (short-lived) + refresh tokens (longer-lived, stored in DB). bcrypt for password hashing.

**Consequences**:
- Stateless request authentication
- Refresh token rotation for security
- Must handle token revocation via database lookup
- Standard approach, well-understood

---

## ADR-005: Real-Time Updates - SSE over WebSocket

**Status**: Accepted  
**Date**: 2026-07-12  

**Context**: Frontend needs real-time workflow execution updates.

**Decision**: Server-Sent Events (SSE) for uni-directional server-to-client updates.

**Consequences**:
- Simpler implementation than WebSocket
- HTTP/2 compatible
- Auto-reconnect built into EventSource API
- Sufficient for workflow status streaming
- If bidirectional communication needed later, can add WebSocket selectively

---

## ADR-006: LLM Abstraction - Provider-Agnostic Interface

**Status**: Accepted  
**Date**: 2026-07-12  

**Context**: The system must support multiple LLM providers (OpenAI, Gemini, Anthropic) with configurable model routing.

**Decision**: Implement a provider abstraction with model routing categories (FAST, REASONING, CRITIC, EMBEDDING, RERANKER). Configuration via environment variables.

**Consequences**:
- No vendor lock-in
- Can use different models for different complexity levels
- Must maintain provider adapters
- Fallback chains for reliability

---

## ADR-007: Frontend Framework - Next.js App Router

**Status**: Accepted  
**Date**: 2026-07-12  

**Context**: Need a modern React framework with server-side capabilities.

**Decision**: Next.js 15 with App Router, TypeScript strict mode, Tailwind CSS, shadcn/ui.

**Consequences**:
- Server components for initial page loads
- Client components for interactivity
- Built-in API routes if needed
- Strong TypeScript integration

---

## ADR-008: Document Processing - PyMuPDF Primary with OCR Fallback

**Status**: Accepted  
**Date**: 2026-07-12  

**Context**: Need reliable PDF text extraction for regulatory documents.

**Decision**: PyMuPDF (fitz) as primary parser for text extraction, heading detection, table extraction. Tesseract/OCRmyPDF as fallback for scanned documents.

**Consequences**:
- Fast primary extraction
- OCR fallback for image-based PDFs
- Must implement quality detection to trigger OCR path
- Page coordinates preserved for citation mapping

---

## ADR-009: Agent Orchestration - LangGraph with Typed State

**Status**: Accepted  
**Date**: 2026-07-12  

**Context**: Need agentic AI orchestration with conditional routing, parallel execution, retries, and human-in-the-loop.

**Decision**: LangGraph as the orchestration layer with typed Pydantic state models, conditional edges, checkpointing, and human interrupt support.

**Consequences**:
- Typed, verifiable agent communication
- Graph visualization matches actual execution topology
- Checkpoint persistence enables resume after failure
- Human interrupts are first-class workflow primitives
- Must carefully design state reducers for parallel execution

---

## ADR-010: Multi-Tenancy - Application-Level Row Isolation

**Status**: Accepted  
**Date**: 2026-07-12  

**Context**: Multiple organizations must have isolated data.

**Decision**: Application-level tenant isolation with organization_id on all tenant-scoped tables. Service layer enforces tenant context. PostgreSQL Row-Level Security as defense-in-depth where feasible.

**Consequences**:
- Simpler than schema-per-tenant
- Must ensure every query includes tenant filter
- RLS provides database-level enforcement
- Shared regulatory documents accessible across tenants
