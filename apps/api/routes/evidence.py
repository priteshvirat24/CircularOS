"""Evidence ledger routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from packages.regulatory_core.models.auth import User
from packages.regulatory_core.models.compliance import (
    EvidenceArtifact, EvidenceAuditEntry, EvidenceStatus,
)

router = APIRouter()


@router.get("")
async def list_evidence(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    obligation_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List evidence artifacts with filtering."""
    query = select(EvidenceArtifact)
    
    if status_filter:
        try:
            query = query.where(EvidenceArtifact.status == EvidenceStatus(status_filter))
        except ValueError:
            pass
    
    if obligation_id:
        query = query.where(EvidenceArtifact.obligation_id == obligation_id)
    
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    query = query.order_by(EvidenceArtifact.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    artifacts = result.scalars().all()
    
    return {
        "evidence": [
            {
                "id": str(a.id),
                "file_name": a.file_name,
                "evidence_type": a.evidence_type,
                "status": a.status.value,
                "freshness_state": a.freshness_state,
                "obligation_id": str(a.obligation_id) if a.obligation_id else None,
                "collection_date": a.collection_date.isoformat() if a.collection_date else None,
                "valid_until": a.valid_until.isoformat() if a.valid_until else None,
                "mapping_confidence": a.mapping_confidence,
                "created_at": a.created_at.isoformat(),
            }
            for a in artifacts
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{evidence_id}")
async def get_evidence(
    evidence_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get evidence artifact details with audit trail."""
    artifact = await db.get(EvidenceArtifact, evidence_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Evidence artifact not found")
    
    # Get audit trail
    audit_result = await db.execute(
        select(EvidenceAuditEntry)
        .where(EvidenceAuditEntry.evidence_artifact_id == evidence_id)
        .order_by(EvidenceAuditEntry.timestamp.desc())
    )
    audit_entries = audit_result.scalars().all()
    
    return {
        "id": str(artifact.id),
        "file_name": artifact.file_name,
        "file_path": artifact.file_path,
        "file_size_bytes": artifact.file_size_bytes,
        "mime_type": artifact.mime_type,
        "sha256_hash": artifact.sha256_hash,
        "evidence_type": artifact.evidence_type,
        "description": artifact.description,
        "status": artifact.status.value,
        "freshness_state": artifact.freshness_state,
        "verification_state": artifact.verification_state,
        "mapping_confidence": artifact.mapping_confidence,
        "collection_date": artifact.collection_date.isoformat() if artifact.collection_date else None,
        "valid_from": artifact.valid_from.isoformat() if artifact.valid_from else None,
        "valid_until": artifact.valid_until.isoformat() if artifact.valid_until else None,
        "review_decision": artifact.review_decision,
        "extracted_facts": artifact.extracted_facts,
        "mapping_rationale": artifact.mapping_rationale,
        "audit_trail": [
            {
                "id": str(e.id),
                "timestamp": e.timestamp.isoformat(),
                "action": e.action,
                "details": e.details,
            }
            for e in audit_entries
        ],
        "created_at": artifact.created_at.isoformat(),
    }
