# CircularOS Architecture

## Agentic Regulatory Intelligence, Compliance Operations, and Supervisory Technology Platform

---

## 1. System Context

```mermaid
graph TB
    subgraph External["External Systems"]
        SEBI["SEBI Public Sources"]
        LLM["LLM Providers<br/>(OpenAI/Gemini/Anthropic)"]
        Langfuse["Langfuse<br/>(Observability)"]
    end

    subgraph Users["Users"]
        CO["Compliance Officer"]
        REV["Reviewer"]
        ADMIN["Org Admin"]
        SUP["Supervisory Viewer"]
    end

    subgraph CircularOS["CircularOS Platform"]
        WEB["Web Application<br/>(Next.js)"]
        API["API Server<br/>(FastAPI)"]
        WORKER["Worker Service<br/>(Celery)"]
        PG["PostgreSQL + pgvector"]
        REDIS["Redis"]
    end

    CO --> WEB
    REV --> WEB
    ADMIN --> WEB
    SUP --> WEB
    WEB --> API
    API --> PG
    API --> REDIS
    API --> WORKER
    WORKER --> PG
    WORKER --> REDIS
    WORKER --> LLM
    WORKER --> SEBI
    API --> LLM
    API --> Langfuse
    WORKER --> Langfuse
```

## 2. Container Architecture

```mermaid
graph TB
    subgraph Frontend["Frontend Container"]
        NEXT["Next.js App Router<br/>TypeScript + Tailwind + shadcn/ui"]
    end

    subgraph Backend["Backend Container"]
        FAST["FastAPI Server<br/>Pydantic v2 + SQLAlchemy 2.x"]
        AUTH["Auth Module<br/>JWT + RBAC"]
        ROUTES["API Routes<br/>/api/v1/*"]
    end

    subgraph Worker["Worker Container"]
        CELERY["Celery Workers"]
        LANGGRAPH["LangGraph Orchestration"]
        AGENTS["Agent Subgraphs"]
        TOOLS["Tool System"]
    end

    subgraph Data["Data Layer"]
        PG["PostgreSQL 16<br/>+ pgvector extension"]
        REDIS["Redis 7<br/>Cache + Broker + Pub/Sub"]
    end

    NEXT -->|REST + SSE| FAST
    FAST --> AUTH
    FAST --> ROUTES
    ROUTES --> PG
    ROUTES --> REDIS
    ROUTES -->|Task Dispatch| CELERY
    CELERY --> LANGGRAPH
    LANGGRAPH --> AGENTS
    AGENTS --> TOOLS
    TOOLS --> PG
    TOOLS --> REDIS
    CELERY --> PG
```

## 3. Monorepo Structure

```
CircularOS/
├── apps/
│   ├── web/                    # Next.js frontend
│   │   ├── src/
│   │   │   ├── app/            # App Router pages
│   │   │   ├── components/     # React components
│   │   │   ├── lib/            # Client utilities
│   │   │   └── hooks/          # Custom hooks
│   │   ├── public/
│   │   └── package.json
│   ├── api/                    # FastAPI backend
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── routes/
│   │   ├── services/
│   │   ├── middleware/
│   │   └── dependencies.py
│   └── worker/                 # Celery workers
│       ├── main.py
│       ├── tasks/
│       └── config.py
├── packages/
│   ├── ai/                     # LLM abstraction layer
│   │   ├── providers/
│   │   ├── prompts/
│   │   └── routing.py
│   ├── agents/                 # LangGraph agents
│   │   ├── supervisor/
│   │   ├── document_intelligence/
│   │   ├── knowledge_extraction/
│   │   ├── regulatory_diff/
│   │   ├── control_evidence/
│   │   ├── compliance_ops/
│   │   └── suptech/
│   ├── regulatory_core/        # Domain models
│   │   ├── models/
│   │   ├── schemas/
│   │   └── enums.py
│   ├── document_processing/    # PDF parsing pipeline
│   │   ├── acquisition.py
│   │   ├── integrity.py
│   │   ├── parser.py
│   │   ├── ocr.py
│   │   └── structure.py
│   ├── retrieval/              # RAG system
│   │   ├── embeddings.py
│   │   ├── search.py
│   │   ├── reranker.py
│   │   └── hybrid.py
│   ├── knowledge_graph/        # Graph operations
│   │   ├── repository.py
│   │   └── queries.py
│   ├── evaluation/             # Eval framework
│   │   ├── runner.py
│   │   ├── metrics.py
│   │   └── datasets.py
│   ├── observability/          # Tracing & logging
│   │   ├── tracing.py
│   │   ├── logging.py
│   │   └── metrics.py
│   └── shared_types/           # Shared Pydantic models
│       ├── events.py
│       └── common.py
├── infra/
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   └── Dockerfile.web
│   └── migrations/
│       ├── env.py
│       └── versions/
├── data/
│   ├── goldsets/
│   └── evaluation/
├── scripts/
│   ├── setup.sh
│   └── seed_demo.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── api/
│   └── e2e/
├── docker-compose.yml
├── .env.example
├── pyproject.toml
├── README.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── DECISIONS.md
├── TASKS.md
├── SECURITY.md
├── EVALUATION.md
└── DEMO.md
```

## 4. Document Ingestion Pipeline

```mermaid
flowchart TD
    A["Source Discovery/<br/>URL Input/<br/>PDF Upload"] --> B["Source Acquisition Agent"]
    B --> C["Integrity Agent<br/>(MIME, SHA-256, Dedup)"]
    C -->|Invalid| D["Reject + Log"]
    C -->|Valid| E["Document Parsing Agent<br/>(PyMuPDF + OCR Fallback)"]
    E --> F["Structure Reconstruction Agent<br/>(Hierarchy, Sections, Clauses)"]
    F --> G["Document Classification Agent<br/>(Type, Domain, Affected Entities)"]
    G --> H["Quality Gate Agent"]
    H -->|Low Quality| I["OCR Reprocessing /<br/>Human Review"]
    H -->|Sufficient| J["Store Document +<br/>Clauses + Embeddings"]
    J --> K["Trigger Downstream:<br/>Extraction / Diff"]
```

## 5. LangGraph Supervisor Architecture

```mermaid
flowchart TD
    SUP["Supervisor Agent"] --> |"classify_request"| CLASSIFY{Workflow Type}
    
    CLASSIFY -->|"ingest"| SG1["Subgraph 1:<br/>Document Intelligence"]
    CLASSIFY -->|"extract"| SG2["Subgraph 2:<br/>Knowledge Extraction"]
    CLASSIFY -->|"diff"| SG3["Subgraph 3:<br/>Regulatory Diff"]
    CLASSIFY -->|"map_controls"| SG4["Subgraph 4:<br/>Control & Evidence"]
    CLASSIFY -->|"plan_compliance"| SG5["Subgraph 5:<br/>Compliance Ops"]
    CLASSIFY -->|"supervise"| SG6["Subgraph 6:<br/>SupTech Intelligence"]
    
    SG1 --> |"document_ready"| SG2
    SG2 --> |"obligations_extracted"| REVIEW{"Human Review<br/>Required?"}
    REVIEW -->|"yes"| HR["Human Review<br/>Interrupt"]
    REVIEW -->|"no"| REG["Obligation Registry"]
    HR -->|"approved"| REG
    HR -->|"rejected"| LOG["Immutable Rejection Log"]
    
    REG --> SG3
    SG3 --> SG4
    SG4 --> SG5
    SG5 --> SG6
```

## 6. Obligation Extraction Subgraph

```mermaid
flowchart TD
    INPUT["Clauses + Context"] --> CA["Clause Analysis Agent<br/>(Classify clause types)"]
    CA --> OE["Obligation Extraction Agent<br/>(Structured extraction)"]
    OE --> CV["Citation Verification Agent<br/>(Verify source spans)"]
    CV --> EV["Entailment Validation Agent<br/>(Semantic entailment check)"]
    EV --> CON["Consistency Agent<br/>(Cross-reference check)"]
    CON --> RC["Regulatory Critic Agent<br/>(Adversarial falsification)"]
    RC --> CONF["Confidence Aggregation Agent"]
    CONF --> GATE{Confidence<br/>Threshold}
    GATE -->|"High"| AUTO["Auto-approve to Registry"]
    GATE -->|"Medium"| REVIEW["Human Review Queue"]
    GATE -->|"Low"| REJECT["Reject with Explanation"]
    REVIEW -->|"Approved"| AUTO
    REVIEW -->|"Rejected"| REJECT
```

## 7. Regulatory Diff Pipeline

```mermaid
flowchart LR
    subgraph Input
        OLD["Previous Document"]
        NEW["New Document"]
    end
    
    OLD --> L1["Level 1: Text Diff"]
    NEW --> L1
    L1 --> L2["Level 2: Structural Diff<br/>(Sections, Clauses)"]
    L2 --> L3["Level 3: Semantic Matching<br/>(Embeddings + Reranking)"]
    L3 --> L4["Level 4: Obligation Diff<br/>(CREATED/MODIFIED/REMOVED)"]
    L4 --> VER["Change Verification Agent"]
    VER --> IMP["Impact Analysis Agent"]
    IMP --> CRIT["Impact Critic Agent"]
    CRIT --> HUMAN{"Material Change?"}
    HUMAN -->|"Yes"| CONFIRM["Human Confirmation"]
    HUMAN -->|"No"| APPLY["Apply Changes"]
    CONFIRM --> APPLY
```

## 8. Evidence Lineage

```mermaid
flowchart TD
    REG["Regulatory Document"] --> CL["Clause"]
    CL --> OB["Obligation"]
    OB --> CTL["Control"]
    OB --> EVR["Evidence Requirement"]
    CTL --> EVA["Evidence Artifact"]
    EVR --> EVA
    EVA --> FRESH{"Freshness Check"}
    FRESH -->|"Valid"| COMP["Compliant"]
    FRESH -->|"Stale"| STALE["Stale - Action Required"]
    FRESH -->|"Missing"| MISS["Missing - Critical Gap"]
```

## 9. Real-Time Event Architecture

```mermaid
sequenceDiagram
    participant W as Worker/Agent
    participant R as Redis Pub/Sub
    participant A as API Server
    participant C as Client (SSE)
    
    W->>R: Publish WorkflowEvent
    W->>A: Persist Event to DB
    R->>A: Event Notification
    A->>C: SSE: AGENT_STARTED
    W->>R: Publish ToolCallEvent
    R->>A: Event Notification
    A->>C: SSE: TOOL_CALLED
    W->>R: Publish CompletionEvent
    R->>A: Event Notification
    A->>C: SSE: AGENT_COMPLETED
```

## 10. Security Architecture

```mermaid
flowchart TD
    REQ["Incoming Request"] --> CORS["CORS Check"]
    CORS --> RL["Rate Limiter"]
    RL --> AUTH["JWT Authentication"]
    AUTH --> RBAC["RBAC Authorization"]
    RBAC --> TENANT["Tenant Isolation<br/>(Org-scoped queries)"]
    TENANT --> VALID["Input Validation<br/>(Pydantic)"]
    VALID --> HANDLER["Request Handler"]
    HANDLER --> AUDIT["Audit Log"]
    HANDLER --> RESP["Response + Security Headers"]
```

## 11. Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Background Processing | Celery + Redis | Lower operational complexity than Temporal for initial deployment |
| Knowledge Graph | PostgreSQL relational tables | Avoid Neo4j dependency; graph abstraction allows future migration |
| Vector Store | pgvector | Single database, reduced operational overhead |
| Auth | JWT with refresh tokens | Stateless, standard, well-supported |
| Real-time | SSE | Simpler than WebSocket for uni-directional event streams |
| Monorepo | Python packages + Next.js | Clean separation, shared types via OpenAPI |

## 12. Scaling Strategy

- **Horizontal**: Celery workers scale independently
- **Database**: Read replicas, connection pooling (pgbouncer)
- **Cache**: Redis cluster for high-throughput caching
- **Search**: pgvector with IVFFlat/HNSW indexes
- **Frontend**: CDN + ISR for static content
- **Agent Pipelines**: Parallel subgraph execution via Celery task groups

## 13. Failure Modes

| Component | Failure Mode | Mitigation |
|-----------|-------------|------------|
| LLM Provider | Timeout/Rate Limit | Retry with backoff, provider fallback chain |
| Document Parsing | Corrupt PDF | Integrity check, OCR fallback, quality gate |
| Agent Pipeline | Infinite Loop | Bounded iteration limits, execution timeouts |
| Database | Connection Exhaustion | Connection pooling, health checks |
| Worker | Process Crash | Celery acks_late, idempotent tasks, checkpointing |
| Embedding | Dimension Mismatch | Provider-specific dimension config, validation |
