"""Audit log routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.dependencies import get_current_user, require_role
from packages.regulatory_core.models.auth import AuditEvent, User, UserRole

router = APIRouter()


@router.get("")
async def list_audit_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = None,
    resource_type: str | None = None,
    user_id: uuid.UUID | None = None,
    user: User = Depends(require_role(UserRole.ORG_ADMIN, UserRole.AUDITOR, UserRole.COMPLIANCE_OFFICER)),
    db: AsyncSession = Depends(get_db),
):
    """List immutable audit events with filtering."""
    query = select(AuditEvent)
    
    if action:
        query = query.where(AuditEvent.action == action)
    if resource_type:
        query = query.where(AuditEvent.resource_type == resource_type)
    if user_id:
        query = query.where(AuditEvent.user_id == user_id)
    
    query = query.order_by(AuditEvent.timestamp.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    return {
        "audit_events": [
            {
                "id": str(e.id),
                "timestamp": e.timestamp.isoformat(),
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "user_id": str(e.user_id) if e.user_id else None,
                "details": e.details,
                "ip_address": e.ip_address,
                "request_id": e.request_id,
            }
            for e in events
        ],
        "page": page,
        "page_size": page_size,
    }
