"""Control library read contracts."""

# ruff: noqa: B008  # FastAPI dependency/query declarations are evaluated by FastAPI.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db, require_demo_read_role
from packages.regulatory_core.models.auth import UserRole
from packages.regulatory_core.models.compliance import Control, ObligationControlMapping

router = APIRouter(prefix="/controls", tags=["controls"])


def _control_payload(control: Control, mapped_obligations: int) -> dict:
    metadata = control.metadata_json or {}
    return {
        "id": str(control.id),
        "name": control.name,
        "description": control.description,
        "control_type": control.control_type,
        "department": control.department,
        "status": control.status,
        "framework": metadata.get("framework"),
        "mapped_obligations": mapped_obligations,
        "source_topic": metadata.get("source_topic"),
    }


@router.get("")
@router.get("/")
async def list_controls(
    framework: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_demo_read_role(UserRole.ORG_ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST, UserRole.REVIEWER, UserRole.AUDITOR)),
) -> dict:
    """Return persisted controls with active obligation-mapping counts."""
    del user
    mapping_count = func.count(ObligationControlMapping.id).filter(ObligationControlMapping.status == "active")
    query = (
        select(Control, mapping_count.label("mapped_obligations"))
        .outerjoin(ObligationControlMapping, ObligationControlMapping.control_id == Control.id)
        .where(Control.deleted_at.is_(None))
        .group_by(Control.id)
        .order_by(Control.created_at.desc())
        .limit(100)
    )
    if framework:
        query = query.where(Control.metadata_json["framework"].astext == framework)
    rows = (await db.execute(query)).all()
    return {"controls": [_control_payload(control, int(count)) for control, count in rows], "total": len(rows)}


@router.get("/{control_id}")
async def get_control(
    control_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_demo_read_role(UserRole.ORG_ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST, UserRole.REVIEWER, UserRole.AUDITOR)),
) -> dict:
    del user
    control = await db.get(Control, control_id)
    if not control or control.deleted_at:
        raise HTTPException(status_code=404, detail="Control not found")
    count = int(
        (
            await db.execute(
                select(func.count()).where(
                    ObligationControlMapping.control_id == control.id,
                    ObligationControlMapping.status == "active",
                )
            )
        ).scalar()
        or 0
    )
    return _control_payload(control, count)
