"""Public, aggregate-only dashboard read model."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from packages.regulatory_core.models.documents import RegulatoryDocument
from packages.regulatory_core.models.evaluation import EvaluationRun
from packages.regulatory_core.models.obligations import (
    DiffRun,
    DiffRunStatus,
    Obligation,
    RegulatoryChange,
)

router = APIRouter()


@router.get("")
async def get_public_dashboard(
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI dependency injection
) -> dict:
    """Serve only public circular metadata and aggregate, non-tenant dashboard signals."""
    documents = list(
        (
            await db.execute(
                select(RegulatoryDocument)
                .where(
                    RegulatoryDocument.is_deleted.is_(False),
                    RegulatoryDocument.organization_id.is_(None),
                )
                .order_by(RegulatoryDocument.issued_date.desc().nullslast())
                .limit(10)
            )
        ).scalars()
    )
    august = next(
        (
            document
            for document in documents
            if (document.issued_date and document.issued_date.year == 2024)
            or "2024-08" in document.title
        ),
        None,
    )
    obligation_total = 0
    if august is not None:
        obligation_total = int(
            (
                await db.execute(
                    select(func.count()).where(
                        Obligation.document_id == august.id,
                        Obligation.deleted_at.is_(None),
                    )
                )
            ).scalar()
            or 0
        )
    diff = (
        await db.execute(
            select(DiffRun)
            .where(DiffRun.status == DiffRunStatus.COMPLETED)
            .order_by(DiffRun.completed_at.desc().nullslast(), DiffRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    evaluation = (
        await db.execute(
            select(EvaluationRun)
            .where(
                EvaluationRun.status == "completed",
                EvaluationRun.run_type == "obligation_extraction",
            )
            .order_by(EvaluationRun.completed_at.desc().nullslast(), EvaluationRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return {
        "documents": [
            {
                "id": str(document.id),
                "title": document.title,
                "reference_number": document.reference_number,
                "status": document.status.value,
                "page_count": document.page_count,
            }
            for document in documents
        ],
        "obligation_total": obligation_total,
        "diff_change_total": int(
            (
                await db.execute(
                    select(func.count()).where(RegulatoryChange.diff_run_id == diff.id)
                )
            ).scalar_one()
            or 0
        )
        if diff
        else None,
        "diff_summary": diff.summary if diff else None,
        "evaluation_f1": evaluation.f1_score if evaluation else None,
        "evaluation_ci": (evaluation.metrics or {}).get("bootstrap_f1_95_ci") if evaluation else None,
    }
