"""Authentication API routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.services import (
    authenticate_user,
    create_access_token,
    create_organization,
    create_refresh_token_value,
    create_user,
    add_user_to_organization,
    store_refresh_token,
    validate_refresh_token,
    revoke_refresh_token,
)
from packages.regulatory_core.models.auth import (
    AuditEvent, Organization, OrganizationMembership, User, UserRole,
)

router = APIRouter()


# ── Request/Response schemas ─────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    organization_name: str = Field(min_length=1, max_length=255)
    organization_slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    entity_type: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict
    organization: dict | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    memberships: list[dict]


# ── Endpoints ────────────────────────────────


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user and organization."""
    # Check if email exists
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    
    # Check if org slug exists
    existing_org = await db.execute(
        select(Organization).where(Organization.slug == body.organization_slug)
    )
    if existing_org.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already taken",
        )
    
    # Create user
    user = await create_user(db, body.email, body.password, body.full_name)
    
    # Create organization
    org = await create_organization(
        db, body.organization_name, body.organization_slug, body.entity_type
    )
    
    # Add user as org admin
    await add_user_to_organization(db, user.id, org.id, UserRole.ORG_ADMIN)
    
    # Generate tokens
    access_token = create_access_token(
        user.id, org.id, UserRole.ORG_ADMIN.value
    )
    refresh_value = create_refresh_token_value()
    await store_refresh_token(
        db, user.id, refresh_value,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    
    # Audit
    audit = AuditEvent(
        organization_id=org.id,
        user_id=user.id,
        action="user.register",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )
    db.add(audit)
    
    from apps.api.config import get_settings
    settings = get_settings()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_value,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
        },
        organization={
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
        },
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return tokens."""
    user = await authenticate_user(db, body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Get user's first membership for org context
    memberships = await db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.is_active == True,
        )
    )
    membership = memberships.scalars().first()
    
    org_id = membership.organization_id if membership else None
    role = membership.role.value if membership else None
    
    access_token = create_access_token(user.id, org_id, role)
    refresh_value = create_refresh_token_value()
    await store_refresh_token(
        db, user.id, refresh_value,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    
    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    
    # Audit
    audit = AuditEvent(
        organization_id=org_id,
        user_id=user.id,
        action="user.login",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )
    db.add(audit)
    
    from apps.api.config import get_settings
    settings = get_settings()
    
    org_data = None
    if membership:
        org = await db.get(Organization, membership.organization_id)
        if org:
            org_data = {"id": str(org.id), "name": org.name, "slug": org.slug}
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_value,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
        },
        organization=org_data,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token (with rotation)."""
    token = await validate_refresh_token(db, body.refresh_token)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    
    # Revoke old token (rotation)
    await revoke_refresh_token(db, token)
    
    # Get user
    user = await db.get(User, token.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Get org context
    memberships = await db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.is_active == True,
        )
    )
    membership = memberships.scalars().first()
    org_id = membership.organization_id if membership else None
    role = membership.role.value if membership else None
    
    # Issue new tokens
    access_token = create_access_token(user.id, org_id, role)
    new_refresh_value = create_refresh_token_value()
    await store_refresh_token(
        db, user.id, new_refresh_value,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    
    from apps.api.config import get_settings
    settings = get_settings()
    
    org_data = None
    if membership:
        org = await db.get(Organization, membership.organization_id)
        if org:
            org_data = {"id": str(org.id), "name": org.name, "slug": org.slug}
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_value,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
        },
        organization=org_data,
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile."""
    memberships_data = []
    for m in user.memberships:
        memberships_data.append({
            "organization_id": str(m.organization_id),
            "role": m.role.value,
            "is_active": m.is_active,
        })
    
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "memberships": memberships_data,
    }
