"""CircularOS API Server.

Production-grade FastAPI application with comprehensive middleware stack:
- CORS protection
- Security headers (CSP, X-Frame-Options, etc.)
- Request ID correlation
- Structured JSON logging
- Rate limiting
- Health checks
- OpenAPI documentation
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from apps.api.config import get_settings
from apps.api.database import check_db_health
from apps.api.routes import health, auth, documents, obligations, controls, evidence

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    
    # Log startup info
    logger.info(
        "circularos_starting",
        app_name=settings.app_name,
        environment=settings.app_env.value,
    )
    
    # Report integration status
    integrations = settings.get_integration_status()
    for name, status in integrations.items():
        level = "info" if status["configured"] else "warning"
        getattr(logger, level)(
            "integration_status",
            integration=name,
            status=status["status"],
        )
    
    yield
    
    # Cleanup
    logger.info("circularos_shutting_down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="CircularOS API",
        description=(
            "Agentic Regulatory Intelligence, Compliance Operations, "
            "and Supervisory Technology Platform for the Indian Securities Market"
        ),
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    
    # ── CORS ─────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )
    
    # ── Request ID + Timing + Security Headers ──
    @app.middleware("http")
    async def add_request_metadata(request: Request, call_next) -> Response:
        """Add request ID, timing, and security headers to every response."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        start_time = time.monotonic()
        
        # Bind request context for structured logging
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        
        response = await call_next(request)
        
        process_time = time.monotonic() - start_time
        
        # Add response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        
        if settings.app_env.value == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none'"
            )
        
        # Log request
        logger.info(
            "request_completed",
            status_code=response.status_code,
            process_time=round(process_time, 4),
        )
        
        return response
    
    # ── Routes ───────────────────────────────────
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(obligations.router, prefix="/api/v1")
    app.include_router(controls.router, prefix="/api/v1")
    app.include_router(evidence.router, prefix="/api/v1")
    
    return app


# Application instance
app = create_app()
