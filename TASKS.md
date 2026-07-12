# CircularOS - Implementation Tasks

## Phase 1: Foundation

### Infrastructure
- [ ] Create monorepo directory structure
- [ ] Create docker-compose.yml (PostgreSQL, Redis, API, Worker, Web)
- [ ] Create .env.example with all configuration variables
- [ ] Create pyproject.toml with dependencies
- [ ] Create Dockerfiles (API, Worker, Web)

### Database
- [ ] Set up SQLAlchemy 2.x async engine
- [ ] Create Alembic migration configuration
- [ ] Design and implement core domain models
- [ ] Create initial migration
- [ ] Run and verify migration

### Authentication & Authorization
- [ ] Implement JWT auth with refresh tokens
- [ ] Implement password hashing (bcrypt)
- [ ] Implement RBAC with 7 roles
- [ ] Implement organization tenancy
- [ ] Create auth API endpoints
- [ ] Test auth flow

### API Foundation
- [ ] Create FastAPI application with middleware
- [ ] Implement health check endpoints
- [ ] Implement CORS, rate limiting, security headers
- [ ] Implement request ID correlation
- [ ] Implement structured JSON logging
- [ ] Implement audit logging

### Worker Foundation
- [ ] Set up Celery with Redis broker
- [ ] Implement task base class with idempotency
- [ ] Implement workflow state persistence
- [ ] Test task execution

---

## Phase 2: Document Ingestion

### Document Processing
- [ ] Implement PDF acquisition (URL download)
- [ ] Implement PDF upload handling
- [ ] Implement SHA-256 integrity verification
- [ ] Implement duplicate detection
- [ ] Implement PyMuPDF text extraction
- [ ] Implement OCR fallback (Tesseract)
- [ ] Implement heading detection
- [ ] Implement table extraction
- [ ] Implement clause hierarchy reconstruction
- [ ] Implement paragraph segmentation

### Document APIs
- [ ] Create document CRUD endpoints
- [ ] Create ingestion endpoint (URL)
- [ ] Create upload endpoint (PDF)
- [ ] Create document processing status endpoint
- [ ] Create clause retrieval endpoints

### Document UI
- [ ] Create document library page
- [ ] Create document viewer page
- [ ] Create ingestion page (URL + upload)
- [ ] Create processing status display

---

## Phase 3: Regulatory Retrieval

### Embedding & Search
- [ ] Implement embedding provider abstraction
- [ ] Implement pgvector storage
- [ ] Implement hierarchy-aware chunking
- [ ] Implement full-text search
- [ ] Implement vector similarity search
- [ ] Implement hybrid search
- [ ] Implement metadata filtering
- [ ] Implement reranking
- [ ] Implement parent-child retrieval
- [ ] Implement neighboring clause expansion

### Research Assistant
- [ ] Implement RAG endpoint
- [ ] Create research chat interface
- [ ] Implement citation display

---

## Phase 4: Agentic Obligation Extraction

### LLM Abstraction
- [ ] Implement provider abstraction (OpenAI, Gemini, Anthropic)
- [ ] Implement model routing (FAST, REASONING, CRITIC)
- [ ] Implement prompt registry with versioning
- [ ] Implement retry policies and circuit breakers
- [ ] Implement fallback chains

### LangGraph Architecture
- [ ] Design typed workflow state models
- [ ] Implement supervisor graph
- [ ] Implement Document Intelligence subgraph
- [ ] Implement Knowledge Extraction subgraph
  - [ ] Clause Analysis Agent
  - [ ] Obligation Extraction Agent
  - [ ] Citation Verification Agent
  - [ ] Entailment Validation Agent
  - [ ] Consistency Agent
  - [ ] Regulatory Critic Agent
  - [ ] Confidence Aggregation Agent
- [ ] Implement checkpointing
- [ ] Implement human interrupt and resume
- [ ] Implement Celery task wrapper

### Review System
- [ ] Create review queue endpoints
- [ ] Create review workbench UI
- [ ] Implement approve/reject/edit actions
- [ ] Create immutable audit trail

### Obligation Registry
- [ ] Create obligation CRUD endpoints
- [ ] Create obligation registry page
- [ ] Create obligation detail page with lineage

---

## Phase 5: Regulatory Diff Engine

### Diff System
- [ ] Implement document text diff (Level 1)
- [ ] Implement structural diff (Level 2)
- [ ] Implement semantic clause matching (Level 3)
- [ ] Implement obligation diff (Level 4)
- [ ] Implement Change Detection Agent
- [ ] Implement Change Verification Agent
- [ ] Implement Impact Analysis Agent
- [ ] Implement Impact Critic Agent
- [ ] Implement human confirmation for material changes

### Diff UI
- [ ] Create regulatory change feed page
- [ ] Create side-by-side diff viewer
- [ ] Create obligation change visualization
- [ ] Create impact analysis display

---

## Phase 6: Compliance Operations

### Controls & Evidence
- [ ] Implement control library
- [ ] Implement control mapping
- [ ] Implement evidence ledger (append-only)
- [ ] Implement evidence upload and verification
- [ ] Implement evidence freshness calculation
- [ ] Implement evidence sufficiency assessment

### Compliance Calendar
- [ ] Implement calendar event generation
- [ ] Implement recurrence calculation
- [ ] Create calendar views (month, week, agenda)
- [ ] Link events to obligations

### Risk Engine
- [ ] Implement weighted risk scoring model
- [ ] Implement risk factor extraction
- [ ] Create risk score explanations
- [ ] Version risk models

---

## Phase 7: SupTech Mirror

- [ ] Implement supervisory aggregation
- [ ] Implement systemic risk signals
- [ ] Create supervisory dashboard
- [ ] Implement drill-down interface
- [ ] Enforce privacy boundaries

---

## Phase 8: Evaluation System

- [ ] Create annotation workbench
- [ ] Implement gold-set storage (JSONL import/export)
- [ ] Implement evaluation runner
- [ ] Implement metrics (precision, recall, F1, MRR, NDCG)
- [ ] Create evaluation dashboard
- [ ] Create dataset management UI

---

## Phase 9: Observability & Security

- [ ] Implement OpenTelemetry tracing
- [ ] Implement agent run explorer
- [ ] Implement prompt injection defenses
- [ ] Implement rate limiting
- [ ] Implement CSP and security headers
- [ ] Create security documentation
- [ ] Implement CI pipeline

---

## Phase 10: Product Polish

- [ ] Build landing page with interactive pipeline
- [ ] Implement Judge Mode guided walkthrough
- [ ] Add loading/empty/error states everywhere
- [ ] Add meaningful animations
- [ ] Responsive design polish
- [ ] Performance optimization
- [ ] Create DEMO.md
- [ ] Create README.md
- [ ] Final documentation pass
