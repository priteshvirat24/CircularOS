"""Auditable obligation registry routes."""

# ruff: noqa: B008  # FastAPI dependency/query declarations are evaluated by FastAPI.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.dependencies import get_db, require_demo_read_role, require_role
from packages.regulatory_core.models.auth import UserRole
from packages.regulatory_core.models.obligations import Obligation, ObligationStatus

router = APIRouter(prefix="/obligations", tags=["obligations"])


class ObligationUpdateRequest(BaseModel):
    normalized_obligation: str | None = None
    actor: str | None = None
    action: str | None = None
    object: str | None = None
    deadline_description: str | None = None
    risk_level: str | None = None
    status: str | None = None


def _verification(obligation: Obligation) -> dict:
    """Expose persisted verification signals without recomputing a verdict in the API."""
    result = obligation.validation_results or {}
    confidence = result.get("confidence") or {}
    return {
        "route": obligation.validation_status,
        "citation_checks": result.get("citation_checks", []),
        "entailment": result.get("entailment_gate", {}),
        "critic": result.get("adversarial_critic") or result.get("critic"),
        "confidence": confidence,
        "confidence_factors": confidence.get("factors", []) if isinstance(confidence, dict) else [],
    }


def _serialize(obligation: Obligation, include_source: bool = False) -> dict:
    payload = {
        "id": str(obligation.id),
        "document_id": str(obligation.document_id),
        "normalized_obligation": obligation.normalized_obligation,
        "actor": obligation.actor,
        "action": obligation.action,
        "object": obligation.object,
        "deadline_description": obligation.deadline_description,
        "risk_level": obligation.risk_level.value if obligation.risk_level else None,
        "status": obligation.status.value,
        "review_status": obligation.review_status,
        "confidence": obligation.confidence,
        "updated_at": obligation.updated_at.isoformat() if obligation.updated_at else None,
        "verification": _verification(obligation),
    }
    if include_source:
        payload["source_text"] = obligation.source_text
        payload["citations"] = [
            {
                "id": str(citation.id),
                "field_name": citation.field_name,
                "cited_text": citation.cited_text,
                "page_number": citation.page_number,
                "char_start": citation.char_start,
                "char_end": citation.char_end,
                "confidence": citation.confidence,
            }
            for citation in obligation.citations
        ]
    return payload


@router.get("")
@router.get("/")
async def list_obligations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    risk_level: str | None = Query(None),
    document_id: UUID | None = Query(None),
    search: str | None = Query(None, min_length=1, max_length=500),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_demo_read_role(UserRole.ORG_ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST, UserRole.REVIEWER)),
) -> dict:
    """List registry rows in bounded pages; never send the full corpus to the browser."""
    del user
    query = select(Obligation).where(Obligation.deleted_at.is_(None))
    if status_filter:
        query = query.where(Obligation.status == status_filter)
    if risk_level:
        query = query.where(Obligation.risk_level == risk_level)
    if document_id:
        query = query.where(Obligation.document_id == document_id)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            Obligation.normalized_obligation.ilike(pattern)
            | Obligation.actor.ilike(pattern)
            | Obligation.action.ilike(pattern)
        )

    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0)
    rows = (
        await db.execute(
            query.options(selectinload(Obligation.citations))
            .order_by(Obligation.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"obligations": [_serialize(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/summary")
async def obligation_summary(
    document_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_demo_read_role(UserRole.ORG_ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST, UserRole.REVIEWER)),
) -> dict:
    """Return small registry rollups for dashboard/evaluation surfaces."""
    del user
    query = select(Obligation.status, Obligation.validation_results).where(Obligation.deleted_at.is_(None))
    if document_id:
        query = query.where(Obligation.document_id == document_id)
    rows = (await db.execute(query)).all()
    citation_checked = 0
    citation_verified = 0
    status_counts: dict[str, int] = {}
    for obligation_status, validation_results in rows:
        name = obligation_status.value
        status_counts[name] = status_counts.get(name, 0) + 1
        checks = (validation_results or {}).get("citation_checks") or []
        if checks:
            citation_checked += 1
            if all(check.get("valid") is True for check in checks):
                citation_verified += 1
    return {
        "total": len(rows),
        "status_counts": status_counts,
        "citation_verification": {
            "verified": citation_verified,
            "checked": citation_checked,
            "rate": citation_verified / citation_checked if citation_checked else None,
        },
    }


@router.get("/{obligation_id}")
async def get_obligation(
    obligation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_demo_read_role(UserRole.ORG_ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST, UserRole.REVIEWER)),
) -> dict:
    del user
    obligation = (
        await db.execute(
            select(Obligation).options(selectinload(Obligation.citations)).where(Obligation.id == obligation_id)
        )
    ).scalar_one_or_none()
    if not obligation or obligation.deleted_at:
        raise HTTPException(status_code=404, detail="Obligation not found")
    return _serialize(obligation, include_source=True)


@router.put("/{obligation_id}")
async def update_obligation(
    obligation_id: UUID,
    update_data: ObligationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role(UserRole.ORG_ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.REVIEWER)),
) -> dict:
    del user
    obligation = await db.get(Obligation, obligation_id)
    if not obligation or obligation.deleted_at:
        raise HTTPException(status_code=404, detail="Obligation not found")
    for key, value in update_data.model_dump(exclude_unset=True).items():
        setattr(obligation, key, value)
    if update_data.status == ObligationStatus.APPROVED.value:
        obligation.review_status = "approved"
    await db.commit()
    await db.refresh(obligation)
    return _serialize(obligation)


@router.delete("/{obligation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_obligation(
    obligation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role(UserRole.COMPLIANCE_OFFICER, UserRole.ORG_ADMIN)),
) -> None:
    del user
    obligation = await db.get(Obligation, obligation_id)
    if not obligation or obligation.deleted_at:
        raise HTTPException(status_code=404, detail="Obligation not found")
    obligation.soft_delete()
    await db.commit()
