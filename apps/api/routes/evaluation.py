"""Read-only evaluation run API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from packages.regulatory_core.models.auth import User
from packages.regulatory_core.models.evaluation import EvaluationDataset, EvaluationRun

router = APIRouter()


@router.get("/runs/{evaluation_run_id}")
async def get_evaluation_run(
    evaluation_run_id: uuid.UUID,
    user: User = Depends(get_current_user),  # noqa: B008 — FastAPI dependency injection
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI dependency injection
) -> dict:
    """Return the persisted evaluation contract; no metric is computed in the route."""
    del user
    run = await db.get(EvaluationRun, evaluation_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="evaluation run not found")
    dataset = await db.get(EvaluationDataset, run.dataset_id)
    metrics = run.metrics or {}
    return {
        "evaluation_run_id": str(run.id),
        "name": run.name,
        "run_type": run.run_type,
        "status": run.status,
        "headline_status": metrics.get("headline_status"),
        "dataset": {
            "id": str(run.dataset_id),
            "name": dataset.name if dataset else None,
            "example_count": dataset.example_count if dataset else None,
        },
        "headline_metrics": {
            "precision": run.precision,
            "recall": run.recall,
            "f1": run.f1_score,
            "detection_rate": metrics.get("detection_rate"),
            "false_positive_rate": metrics.get("false_positive_rate"),
        },
        "confusion": metrics.get("confusion"),
        "matcher_config": metrics.get("matcher_config"),
        "field_accuracy": metrics.get("field_accuracy"),
        "difficulty_breakdown": metrics.get("difficulty_breakdown"),
        "bootstrap_f1_95_ci": metrics.get("bootstrap_f1_95_ci"),
        "named_failures": metrics.get("named_failures", []),
        "corpus_coverage": metrics.get("corpus_coverage"),
        "extraction_provenance": metrics.get("extraction_provenance"),
        "verification_provenance": metrics.get("verification_provenance"),
        "calibration": metrics.get("calibration"),
        "calibrated_routing_split": metrics.get("calibrated_routing_split"),
        "ground_truth_note": metrics.get("ground_truth_note"),
        "usage": {
            "total_tokens": run.total_tokens,
            "total_cost_usd": run.total_cost_usd,
            "accounting": metrics.get("token_cost_accounting"),
        },
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
