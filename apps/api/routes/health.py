"""Health check endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter

from apps.api.config import get_settings
from apps.api.database import check_db_health

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check for load balancer / container orchestrator."""
    return {
        "status": "healthy",
        "service": "circularos-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def readiness_check():
    """Deep readiness check verifying all critical dependencies."""
    settings = get_settings()
    checks = {}
    overall_healthy = True
    
    # Database check
    db_status = await check_db_health()
    checks["database"] = db_status
    if db_status["status"] != "healthy":
        overall_healthy = False
    
    # Redis check
    try:
        redis_client = aioredis.from_url(settings.redis_url)
        await redis_client.ping()
        checks["redis"] = {"status": "healthy"}
        await redis_client.aclose()
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # Integration status
    checks["integrations"] = settings.get_integration_status()
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "service": "circularos-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.get("/health/integrations")
async def integration_status():
    """Report which external integrations are configured."""
    settings = get_settings()
    return {
        "integrations": settings.get_integration_status(),
    }
