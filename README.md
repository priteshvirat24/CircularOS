# CircularOS
**Agentic Regulatory Intelligence, Compliance Operations, and Supervisory Technology Platform**

CircularOS is a production-grade, asynchronous, event-driven RegTech platform designed for the complex regulatory landscape of the Indian Securities Market (SEBI, RBI, NSE, BSE). It converts unstructured regulatory circulars and notifications into structured, machine-actionable obligations with full provenance, maps them to internal controls, and provides an elegant human-in-the-loop (HITL) review interface.

---

## 🏛️ System Architecture

The system is built as a highly scalable Python/TypeScript monorepo. It features a microservice-inspired architecture running on a unified codebase, separating the fast synchronous web server from heavy asynchronous AI workloads.

### High-Level Components

1. **FastAPI Backend (`apps/api`)**: The core entry point for the frontend. Handles authentication, RBAC, CRUD operations, and initiates background tasks.
2. **Celery Task Worker (`apps/worker`)**: Handles long-running, I/O bound tasks including PDF processing, OCR, and AI agent orchestration.
3. **Next.js Web Application (`apps/web`)**: A premium, glassmorphic UI built with React 18, Tailwind CSS, and Next.js App Router for compliance officers to interface with the data.
4. **Agentic Engine (`packages/ai`)**: The core intelligence layer powered by LangGraph, abstracting multi-agent orchestration and LLM integrations.
5. **PostgreSQL + pgvector**: The primary data store, using SQLAlchemy 2.0 with asynchronous drivers (`asyncpg`) and `uuid7` for time-sortable relational data and vector embeddings.
6. **Redis**: Used as the Celery message broker, application cache, and distributed lock manager for rate-limiting.

---

## 🤖 Agentic AI & LangGraph Topologies

CircularOS leverages **LangGraph** to build stateful, multi-actor applications with LLMs. Unlike simple zero-shot prompting, CircularOS uses complex Directed Acyclic Graphs (DAGs) to process regulatory text.

### The Supervisor Pattern
A top-level Supervisor Agent routes documents through various subgraphs based on the current context:
- **Document Intelligence Subgraph**: 
  - *Document Classifier*: Identifies the issuing authority and document type using a fast model (e.g., `gpt-4o-mini`).
  - *Clause Classifier*: Evaluates individual paragraphs to determine if they contain actionable compliance obligations.
  - *Obligation Extractor*: Uses reasoning models (`gpt-4o`) to extract highly structured JSON objects (Actor, Action, Object, Deadline, Risk Level) directly linked to source citations.
- **Knowledge Extraction Subgraph**: 
  - Takes the extracted obligations and autonomously maps them to internal control frameworks (e.g., ISO 27001, SOC 2).

### AI Resilience (`packages/ai/resilience.py`)
All LLM API calls are wrapped in robust Circuit Breakers and exponential backoff retry logic (via `tenacity`) to gracefully handle provider outages and rate-limiting (HTTP 429/500 errors).

---

## 🛠️ Technology Stack

### Backend
- **Python 3.12+**: Utilizing modern typing and async paradigms.
- **FastAPI**: High-performance asynchronous REST API framework.
- **SQLAlchemy 2.0**: The premier Python ORM, operating in fully asynchronous mode via `asyncpg`.
- **Alembic**: Database migration management.
- **Celery**: Distributed task queue for executing LangGraph workflows.
- **PyMuPDF & Tesseract**: For advanced, spatial-aware document parsing and OCR.

### Frontend
- **Next.js 14+ (App Router)**: Server-side rendering and robust routing.
- **React 18**: Component-based UI library.
- **Tailwind CSS v4**: Utility-first styling.
- **Lucide React**: Premium iconography.
- **Axios**: API client integration.

### Infrastructure & DevOps
- **Docker & Docker Compose**: Containerized development and deployment.
- **PostgreSQL 16**: Relational database.
- **Redis 7**: In-memory data structure store.

---

## 🔒 Security & Compliance Design

As a RegTech platform, CircularOS enforces strict security measures:
- **Authentication**: JWT-based access tokens with strict refresh token rotation.
- **Password Security**: Standard bcrypt hashing.
- **Role-Based Access Control (RBAC)**: Fine-grained permissions featuring 7 distinct roles (Super Admin, Org Admin, Compliance Officer, Reviewer, Analyst, Auditor, Supervisory Viewer).
- **Organization Tenancy**: Strict logical separation of data using `organization_id` boundaries on all multi-tenant models.
- **Audit Trails**: Extensive logging and a dedicated `AuditLog` domain model tracking every mutation.
- **Soft Deletion**: Records are never hard-deleted; instead, `deleted_at` and `deleted_by` fields maintain historical integrity.

---

## 🚀 Quick Start

```bash
# 1. Clone and set up environment
git clone https://github.com/priteshvirat24/CircularOS.git
cd CircularOS
cp .env.example .env
# Ensure you configure your OPENAI_API_KEY in .env

# 2. Start core infrastructure (PostgreSQL & Redis)
docker compose up -d postgres redis

# 3. Setup Python Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 4. Run database migrations
alembic upgrade head

# 5. Start API server
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

# 6. Start Celery worker (in separate terminal)
source .venv/bin/activate
celery -A apps.worker.main worker --loglevel=info

# 7. Start Next.js Frontend (in separate terminal)
cd apps/web 
npm install 
npm run dev
```

### Accessing the System
- **Web UI**: `http://localhost:3000`
- **FastAPI Swagger**: `http://localhost:8000/api/docs`

---

## 📈 Database Schema (Domain Models)

The domain is heavily structured to maintain a "Single Source of Truth":
- **Auth**: `User`, `Organization`
- **Documents**: `RegulatoryDocument`, `DocumentPage`, `Clause`
- **Obligations**: `Obligation`, `ReviewTask`
- **Compliance**: `Control`, `Evidence`
- **Agent Traces**: `ExtractionRun`, `AgentRun` (For LangGraph observability)

All primary keys utilize **UUIDv7**, ensuring they are time-sortable and optimized for database indexing while avoiding sequential ID guessing attacks.

---
*Built for the future of Agentic RegTech.*
