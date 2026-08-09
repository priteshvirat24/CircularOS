from __future__ import annotations

import uuid
from datetime import UTC, datetime

from apps.api.database import async_session_maker
from apps.api.dependencies import get_current_user
from packages.regulatory_core.models.evaluation import EvaluationDataset, EvaluationRun


async def _seed_run() -> uuid.UUID:
    marker = uuid.uuid4().hex
    async with async_session_maker() as db:
        dataset = EvaluationDataset(
            name=f"api-eval-{marker}",
            dataset_type="obligation_extraction",
            example_count=1,
        )
        db.add(dataset)
        await db.flush()
        run = EvaluationRun(
            dataset_id=dataset.id,
            name="PARTIAL fixture evaluation",
            run_type="obligation_extraction",
            status="completed",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            precision=0.5,
            recall=0.4,
            f1_score=4 / 9,
            total_tokens=12,
            total_cost_usd=0.0,
            metrics={
                "headline_status": "PARTIAL",
                "confusion": {"true_positives": 2, "false_positives": 2, "false_negatives": 3},
                "field_accuracy": {"actor": 1.0},
                "named_failures": [{"gold_id": "fixture-failure"}],
                "corpus_coverage": {"status": "PARTIAL", "evaluated_examples": 5},
                "token_cost_accounting": {"complete": True},
                "ground_truth_note": "single-annotator fixture",
            },
        )
        db.add(run)
        await db.commit()
        return run.id


async def test_get_evaluation_run_returns_persisted_contract(client, app) -> None:
    run_id = await _seed_run()
    app.dependency_overrides[get_current_user] = lambda: object()
    try:
        response = client.get(f"/api/v1/evaluation/runs/{run_id}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["headline_status"] == "PARTIAL"
    assert payload["headline_metrics"]["precision"] == 0.5
    assert payload["confusion"]["true_positives"] == 2
    assert payload["corpus_coverage"]["status"] == "PARTIAL"
    assert payload["named_failures"][0]["gold_id"] == "fixture-failure"
    assert payload["usage"]["total_tokens"] == 12


async def test_get_evaluation_run_404(client, app) -> None:
    app.dependency_overrides[get_current_user] = lambda: object()
    try:
        response = client.get(f"/api/v1/evaluation/runs/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 404
