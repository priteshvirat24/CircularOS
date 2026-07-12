"""FastAPI dependencies for authentication and authorization."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.services import decode_access_token, get_user_by_id
from packages.regulatory_core.models.auth import User, UserRole

security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None
    
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
        user = await get_user_by_id(db, user_id)
        if user:
            # Attach org context from token
            user._current_org_id = payload.get("org_id")
            user._current_role = payload.get("role")
        return user
    except (ValueError, KeyError):
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require authenticated user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Attach org context from token
    user._current_org_id = payload.get("org_id")
    user._current_role = payload.get("role")
    return user


def require_role(*roles: UserRole):
    """Create a dependency that requires specific roles."""
    
    async def _check_role(user: User = Depends(get_current_user)) -> User:
        if user.is_superuser:
            return user
        
        current_role = getattr(user, "_current_role", None)
        if current_role and UserRole(current_role) in roles:
            return user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required roles: {[r.value for r in roles]}",
        )
    
    return _check_role


def get_org_id(user: User = Depends(get_current_user)) -> uuid.UUID:
    """Extract organization ID from the current user's token context."""
    org_id = getattr(user, "_current_org_id", None)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context required. Include org_id in token.",
        )
    return uuid.UUID(org_id)
