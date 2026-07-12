"""Review queue and workbench routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.dependencies import get_current_user, get_org_id
from packages.regulatory_core.models.auth import AuditEvent, User
from packages.regulatory_core.models.obligations import (
    Obligation, ObligationStatus, ReviewAction, ReviewDecision, ReviewTask,
)

router = APIRouter()


class ReviewActionRequest(BaseModel):
    action: str  # approve, reject, edit_and_approve, request_reprocessing, escalate
    comment: str | None = None
    edits: dict | None = None


@router.get("")
async def list_review_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str = Query("pending", alias="status"),
    task_type: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List review tasks in the queue."""
    query = select(ReviewTask).where(ReviewTask.status == status_filter)
    
    if task_type:
        query = query.where(ReviewTask.task_type == task_type)
    
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    query = query.order_by(ReviewTask.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    return {
        "reviews": [
            {
                "id": str(t.id),
                "task_type": t.task_type,
                "priority": t.priority,
                "status": t.status,
                "obligation_id": str(t.obligation_id) if t.obligation_id else None,
                "assigned_to": str(t.assigned_to) if t.assigned_to else None,
                "context": t.context,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/{review_id}/decision", status_code=status.HTTP_200_OK)
async def submit_review_decision(
    review_id: uuid.UUID,
    body: ReviewActionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a review decision (approve, reject, edit, etc.)."""
    task = await db.get(ReviewTask, review_id)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")
    
    if task.status != "pending":
        raise HTTPException(status_code=400, detail="Review task is not pending")
    
    try:
        action = ReviewAction(body.action)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action: {body.action}")
    
    # Create immutable decision record
    previous_state = None
    new_state = None
    
    if task.obligation_id:
        obl = await db.get(Obligation, task.obligation_id)
        if obl:
            previous_state = {
                "status": obl.status.value,
                "review_status": obl.review_status,
            }
            
            # Apply decision
            if action == ReviewAction.APPROVE:
                obl.status = ObligationStatus.APPROVED
                obl.review_status = "approved"
            elif action == ReviewAction.REJECT:
                obl.status = ObligationStatus.REJECTED
                obl.review_status = "rejected"
            elif action == ReviewAction.EDIT_AND_APPROVE:
                if body.edits:
                    for field, value in body.edits.items():
                        if hasattr(obl, field):
                            setattr(obl, field, value)
                obl.status = ObligationStatus.APPROVED
                obl.review_status = "approved_with_edits"
            elif action == ReviewAction.REQUEST_REPROCESSING:
                obl.status = ObligationStatus.CANDIDATE
                obl.review_status = "reprocessing_requested"
            elif action == ReviewAction.ESCALATE:
                obl.review_status = "escalated"
            
            obl.reviewer_id = user.id
            obl.reviewed_at = datetime.now(timezone.utc)
            
            new_state = {
                "status": obl.status.value,
                "review_status": obl.review_status,
            }
    
    decision = ReviewDecision(
        review_task_id=task.id,
        reviewer_id=user.id,
        action=action,
        comment=body.comment,
        edits=body.edits,
        previous_state=previous_state,
        new_state=new_state,
    )
    db.add(decision)
    
    task.status = "completed"
    
    # Audit event
    audit = AuditEvent(
        user_id=user.id,
        action=f"review.{body.action}",
        resource_type="review_task",
        resource_id=str(review_id),
        details={
            "obligation_id": str(task.obligation_id) if task.obligation_id else None,
            "action": body.action,
            "comment": body.comment,
        },
    )
    db.add(audit)
    
    return {
        "review_id": str(review_id),
        "decision_id": str(decision.id),
        "action": body.action,
        "status": "completed",
    }
