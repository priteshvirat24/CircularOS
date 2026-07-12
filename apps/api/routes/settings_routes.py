"""Settings and configuration routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.config import get_settings
from apps.api.dependencies import get_current_user, require_role
from packages.regulatory_core.models.auth import User, UserRole

router = APIRouter()


@router.get("")
async def get_system_settings(
    user: User = Depends(require_role(UserRole.ORG_ADMIN)),
):
    """Get system settings and integration status."""
    settings = get_settings()
    
    return {
        "app": {
            "name": settings.app_name,
            "environment": settings.app_env.value,
            "debug": settings.app_debug,
        },
        "integrations": settings.get_integration_status(),
        "models": {
            "fast": {
                "provider": settings.fast_model_provider,
                "model": settings.fast_model_name,
            },
            "reasoning": {
                "provider": settings.reasoning_model_provider,
                "model": settings.reasoning_model_name,
            },
            "critic": {
                "provider": settings.critic_model_provider,
                "model": settings.critic_model_name,
            },
            "embedding": {
                "provider": settings.embedding_provider,
                "model": settings.embedding_model,
                "dimensions": settings.embedding_dimensions,
            },
        },
        "limits": {
            "max_upload_size_mb": settings.max_upload_size_mb,
            "rate_limit_per_minute": settings.rate_limit_per_minute,
        },
    }
