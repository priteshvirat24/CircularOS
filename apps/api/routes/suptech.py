"""Read-only supervisory aggregation endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from packages.regulatory_core.models.auth import User
from packages.suptech.access import SupTechAccess, SupTechDataError
from packages.suptech.aggregation import (
    build_adoption_view,
    build_gap_view,
    build_posture_view,
)
from packages.suptech.types import MarketInput

router = APIRouter()


async def _authorized_market(
    db: AsyncSession, user: User, circular_id: uuid.UUID | None = None
) -> MarketInput:
    try:
        access = await SupTechAccess.authorize(db, user)
        return await access.load_market(circular_id)
    except SupTechDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get("/posture")
async def get_market_posture(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return aggregate posture cards and a market-wide rollup."""
    return build_posture_view(await _authorized_market(db, user))


@router.get("/adoption/{circular_id}")
async def get_circular_adoption(
    circular_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return operationalization status for material new/modified circular changes."""
    return build_adoption_view(await _authorized_market(db, user, circular_id))


@router.get("/gaps/{gap_key}")
async def get_systemic_gap(
    gap_key: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return affected intermediary names and posture for one aggregate gap key."""
    market = await _authorized_market(db, user)
    result = build_gap_view(market, gap_key)
    if result is None:
        raise HTTPException(status_code=404, detail="Systemic gap not found")
    return result
