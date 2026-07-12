"""Organization management routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.dependencies import get_current_user, require_role
from packages.regulatory_core.models.auth import (
    Organization, OrganizationMembership, User, UserRole,
)

router = APIRouter()


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    entity_type: str | None
    description: str | None
    is_active: bool


@router.get("")
async def list_organizations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List organizations the current user belongs to."""
    org_ids = [m.organization_id for m in user.memberships if m.is_active]
    if not org_ids:
        return {"organizations": []}
    
    result = await db.execute(
        select(Organization).where(
            Organization.id.in_(org_ids),
            Organization.is_deleted == False,
        )
    )
    orgs = result.scalars().all()
    
    return {
        "organizations": [
            {
                "id": str(o.id),
                "name": o.name,
                "slug": o.slug,
                "entity_type": o.entity_type,
                "description": o.description,
                "is_active": o.is_active,
            }
            for o in orgs
        ]
    }


@router.get("/{org_id}")
async def get_organization(
    org_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get organization details (requires membership)."""
    # Check membership
    has_access = any(
        m.organization_id == org_id and m.is_active
        for m in user.memberships
    )
    if not has_access and not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    org = await db.get(Organization, org_id)
    if not org or org.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "entity_type": org.entity_type,
        "description": org.description,
        "is_active": org.is_active,
        "settings": org.settings,
    }
