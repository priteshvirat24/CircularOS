"""API route registry for CircularOS."""

from __future__ import annotations

from fastapi import APIRouter

from apps.api.routes.health import router as health_router
from apps.api.routes.auth import router as auth_router
from apps.api.routes.organizations import router as org_router
from apps.api.routes.documents import router as docs_router
from apps.api.routes.obligations import router as obligations_router
from apps.api.routes.reviews import router as reviews_router
from apps.api.routes.evidence import router as evidence_router
from apps.api.routes.agents import router as agents_router
from apps.api.routes.audit import router as audit_router
from apps.api.routes.settings_routes import router as settings_router

router = APIRouter()

# Health & system
router.include_router(health_router, prefix="/api/v1", tags=["health"])

# Authentication
router.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

# Organizations
router.include_router(org_router, prefix="/api/v1/organizations", tags=["organizations"])

# Documents
router.include_router(docs_router, prefix="/api/v1/documents", tags=["documents"])

# Obligations
router.include_router(obligations_router, prefix="/api/v1/obligations", tags=["obligations"])

# Reviews
router.include_router(reviews_router, prefix="/api/v1/reviews", tags=["reviews"])

# Evidence
router.include_router(evidence_router, prefix="/api/v1/evidence", tags=["evidence"])

# Agent workflows
router.include_router(agents_router, prefix="/api/v1/agents", tags=["agents"])

# Audit
router.include_router(audit_router, prefix="/api/v1/audit", tags=["audit"])

# Settings
router.include_router(settings_router, prefix="/api/v1/settings", tags=["settings"])
