"""Authentication service: JWT tokens, password hashing, user management."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import hashlib
import secrets

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import get_settings
from packages.regulatory_core.models.auth import (
    User, Organization, OrganizationMembership, RefreshToken, UserRole,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: uuid.UUID,
    organization_id: Optional[uuid.UUID] = None,
    role: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    if organization_id:
        payload["org_id"] = str(organization_id)
    if role:
        payload["role"] = role
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token_value() -> str:
    """Generate a secure random refresh token value."""
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    """Hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Optional[User]:
    """Authenticate a user by email and password."""
    result = await db.execute(
        select(User).where(User.email == email, User.is_active == True, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if user and verify_password(password, user.hashed_password):
        return user
    return None


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Fetch a user by ID."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True, User.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str,
    is_superuser: bool = False,
) -> User:
    """Create a new user."""
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        is_superuser=is_superuser,
    )
    db.add(user)
    await db.flush()
    return user


async def create_organization(
    db: AsyncSession,
    name: str,
    slug: str,
    entity_type: Optional[str] = None,
    description: Optional[str] = None,
) -> Organization:
    """Create a new organization."""
    org = Organization(
        name=name,
        slug=slug,
        entity_type=entity_type,
        description=description,
    )
    db.add(org)
    await db.flush()
    return org


async def add_user_to_organization(
    db: AsyncSession,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role: UserRole = UserRole.ANALYST,
) -> OrganizationMembership:
    """Add a user to an organization with a role."""
    membership = OrganizationMembership(
        user_id=user_id,
        organization_id=organization_id,
        role=role,
    )
    db.add(membership)
    await db.flush()
    return membership


async def store_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    token_value: str,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> RefreshToken:
    """Store a refresh token hash in the database."""
    settings = get_settings()
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=hash_token(token_value),
        expires_at=datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_refresh_token_expire_days
        ),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(refresh_token)
    await db.flush()
    return refresh_token


async def validate_refresh_token(
    db: AsyncSession, token_value: str
) -> Optional[RefreshToken]:
    """Validate a refresh token and return it if valid."""
    token_hash = hash_token(token_value)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(db: AsyncSession, token: RefreshToken) -> None:
    """Revoke a refresh token."""
    token.is_revoked = True
    token.revoked_at = datetime.now(timezone.utc)
    await db.flush()
