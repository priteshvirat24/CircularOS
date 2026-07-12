from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from apps.api.dependencies import get_db, require_role
from packages.regulatory_core.models.compliance import Control, Evidence
from packages.regulatory_core.auth.rbac import Role

router = APIRouter(prefix="/controls", tags=["controls"])

class ControlResponse(BaseModel):
    id: UUID
    control_code: str
    description: str
    owner_id: Optional[UUID]
    framework: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ControlResponse])
async def list_controls(
    framework: Optional[str] = Query(None, description="Filter by framework"),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role([Role.COMPLIANCE_OFFICER, Role.ANALYST, Role.REVIEWER, Role.AUDITOR]))
):
    """List controls from the library."""
    query = select(Control).where(Control.deleted_at.is_(None))
    
    if framework:
        query = query.where(Control.framework == framework)
        
    result = await db.execute(query.order_by(Control.control_code).limit(100))
    return result.scalars().all()


@router.get("/{control_id}", response_model=ControlResponse)
async def get_control(
    control_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role([Role.COMPLIANCE_OFFICER, Role.ANALYST, Role.REVIEWER, Role.AUDITOR]))
):
    """Get a specific control by ID."""
    control = await db.get(Control, control_id)
    if not control or control.deleted_at:
        raise HTTPException(status_code=404, detail="Control not found")
    return control
