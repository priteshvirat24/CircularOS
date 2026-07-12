from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from apps.api.dependencies import get_db, require_role
from packages.regulatory_core.models.obligations import Obligation, ObligationStatus, ReviewTask
from packages.regulatory_core.auth.rbac import Role

router = APIRouter(prefix="/obligations", tags=["obligations"])

class ObligationResponse(BaseModel):
    id: UUID
    document_id: UUID
    source_text: str
    normalized_obligation: str
    actor: str
    action: str
    object: Optional[str]
    deadline_description: Optional[str]
    risk_level: str
    status: str
    review_status: str

    class Config:
        from_attributes = True

class ObligationUpdateRequest(BaseModel):
    normalized_obligation: Optional[str] = None
    actor: Optional[str] = None
    action: Optional[str] = None
    object: Optional[str] = None
    deadline_description: Optional[str] = None
    risk_level: Optional[str] = None
    status: Optional[str] = None


@router.get("/", response_model=List[ObligationResponse])
async def list_obligations(
    status: Optional[str] = Query(None, description="Filter by status (e.g., approved, candidate)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role([Role.COMPLIANCE_OFFICER, Role.ANALYST, Role.REVIEWER]))
):
    """List obligations with optional filtering."""
    query = select(Obligation).where(Obligation.deleted_at.is_(None))
    
    if status:
        query = query.where(Obligation.status == status)
    if risk_level:
        query = query.where(Obligation.risk_level == risk_level)
        
    result = await db.execute(query.order_by(Obligation.created_at.desc()).limit(100))
    return result.scalars().all()


@router.get("/{obligation_id}", response_model=ObligationResponse)
async def get_obligation(
    obligation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role([Role.COMPLIANCE_OFFICER, Role.ANALYST, Role.REVIEWER]))
):
    """Get a specific obligation by ID."""
    obligation = await db.get(Obligation, obligation_id)
    if not obligation or obligation.deleted_at:
        raise HTTPException(status_code=404, detail="Obligation not found")
    return obligation


@router.put("/{obligation_id}", response_model=ObligationResponse)
async def update_obligation(
    obligation_id: UUID,
    update_data: ObligationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role([Role.COMPLIANCE_OFFICER, Role.REVIEWER]))
):
    """Update an obligation (e.g., after human review)."""
    obligation = await db.get(Obligation, obligation_id)
    if not obligation or obligation.deleted_at:
        raise HTTPException(status_code=404, detail="Obligation not found")
        
    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        return obligation
        
    for key, value in update_dict.items():
        setattr(obligation, key, value)
        
    # If status changes to APPROVED, update review_status as well
    if update_dict.get("status") == ObligationStatus.APPROVED.value:
        obligation.review_status = "approved"
        
    await db.commit()
    await db.refresh(obligation)
    return obligation


@router.delete("/{obligation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_obligation(
    obligation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role([Role.COMPLIANCE_OFFICER, Role.ORG_ADMIN]))
):
    """Soft delete an obligation."""
    obligation = await db.get(Obligation, obligation_id)
    if not obligation or obligation.deleted_at:
        raise HTTPException(status_code=404, detail="Obligation not found")
        
    from datetime import datetime, timezone
    obligation.deleted_at = datetime.now(timezone.utc)
    obligation.deleted_by = user.id
    await db.commit()
