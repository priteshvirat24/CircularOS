# CircularOS

**Agentic Regulatory Intelligence, Compliance Operations, and Supervisory Technology Platform for the Indian Securities Market**

CircularOS converts regulatory circulars into structured, machine-actionable obligations with full provenance, detects regulatory changes, maps controls and evidence, and provides supervisory visibility.

## Quick Start

```bash
# 1. Clone and set up environment
cp .env.example .env
# Edit .env with your configuration

# 2. Start infrastructure
docker compose up -d postgres redis

# 3. Install Python dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 4. Run database migrations
alembic upgrade head

# 5. Start API server
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

# 6. Start worker (in separate terminal)
celery -A apps.worker.main worker --loglevel=info

# 7. Start frontend (in separate terminal)
cd apps/web && npm install && npm run dev
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system architecture.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture and design
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - Implementation phases
- [DECISIONS.md](DECISIONS.md) - Architecture decision records
- [TASKS.md](TASKS.md) - Implementation task tracking

## API Documentation

When the API server is running:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
- OpenAPI JSON: http://localhost:8000/api/openapi.json

## License

MIT
