"""Regulatory diff routes — trigger a diff and fetch its cited, materiality-scored change-list."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.dependencies import get_current_user, get_current_user_optional
from apps.api.services.diff_service import run_diff_async
from packages.regulatory_core.models.auth import User
from packages.regulatory_core.models.documents import RegulatoryDocument
from packages.regulatory_core.models.obligations import DiffRun, RegulatoryChange

router = APIRouter()


class TriggerDiffRequest(BaseModel):
    old_document_id: uuid.UUID
    new_document_id: uuid.UUID


def _change_to_dict(c: RegulatoryChange) -> dict:
    details = c.diff_details or {}
    return {
        "id": str(c.id),
        "change_type": c.change_type.value,
        "obligation": details.get("obligation"),
        "changed_fields": c.changed_fields or [],
        "old_ref": details.get("old_ref"),
        "new_ref": details.get("new_ref"),
        "old_text": c.old_text,
        "new_text": c.new_text,
        "materiality": c.materiality.value if c.materiality else None,
        "materiality_reasons": c.materiality_reasons or [],
        "confidence": c.confidence,
        "similarity_score": c.similarity_score,
        "requires_confirmation": c.requires_confirmation,
        "review_status": c.review_status,
        "citations": details.get("citations", {}),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def trigger_diff(
    body: TriggerDiffRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run the diff engine on two documents and persist the change-list. Returns the run summary.

    Runs synchronously — the deterministic engine completes in ~1s on a full master circular, so
    the caller gets the result immediately. (The same entrypoint is exposed as a Celery task for
    background execution.)
    """
    if body.old_document_id == body.new_document_id:
        raise HTTPException(status_code=400, detail="old and new documents must differ")
    for doc_id in (body.old_document_id, body.new_document_id):
        doc = await db.get(RegulatoryDocument, doc_id)
        if not doc or getattr(doc, "is_deleted", False):
            raise HTTPException(status_code=404, detail=f"document {doc_id} not found")

    try:
        diff_run_id = await run_diff_async(
            str(body.old_document_id), str(body.new_document_id), created_by=str(user.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    run = await db.get(DiffRun, uuid.UUID(diff_run_id))
    return {
        "diff_run_id": diff_run_id,
        "status": run.status.value if run else "unknown",
        "summary": run.summary if run else None,
    }


@router.get("")
async def list_diff_runs(
    limit: int = Query(20, ge=1, le=100),
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List recent diff runs (newest first)."""
    runs = (
        await db.execute(select(DiffRun).order_by(DiffRun.created_at.desc()).limit(limit))
    ).scalars().all()
    return {
        "diff_runs": [
            {
                "diff_run_id": str(r.id),
                "old_document_id": str(r.old_document_id),
                "new_document_id": str(r.new_document_id),
                "status": r.status.value,
                "summary": r.summary,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ],
        "total": len(runs),
    }


@router.get("/{diff_run_id}")
async def get_diff(
    diff_run_id: uuid.UUID,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a diff run's full change-list in the documented output contract."""
    run = await db.get(DiffRun, diff_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="diff run not found")

    old_doc = await db.get(RegulatoryDocument, run.old_document_id)
    new_doc = await db.get(RegulatoryDocument, run.new_document_id)

    changes = (
        await db.execute(
            select(RegulatoryChange)
            .where(RegulatoryChange.diff_run_id == diff_run_id)
            .order_by(RegulatoryChange.requires_confirmation.desc(),
                      RegulatoryChange.change_type)
        )
    ).scalars().all()

    return {
        "diff_run_id": str(run.id),
        "status": run.status.value,
        "old_document": {"id": str(run.old_document_id),
                         "title": old_doc.title if old_doc else None},
        "new_document": {"id": str(run.new_document_id),
                         "title": new_doc.title if new_doc else None},
        "summary": run.summary,
        "matcher": run.matcher_config,
        "notes": run.notes or [],
        "changes": [_change_to_dict(c) for c in changes],
    }
