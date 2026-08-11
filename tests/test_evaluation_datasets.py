"""Gold-set loader identity and history-safety tests."""

from __future__ import annotations

from sqlalchemy import select

from apps.api.database import async_session_maker
from packages.evaluation.datasets import _upsert_examples
from packages.regulatory_core.models.evaluation import EvaluationDataset, EvaluationExample


def _values(gold_id: str, quote: str) -> dict:
    return {
        "input_data": {"gold_id": gold_id, "exact_quote": quote},
        "expected_output": {"is_obligation": True},
        "tags": ["fixture"],
    }


async def test_goldset_reload_updates_in_place_without_replacing_example_id() -> None:
    async with async_session_maker() as db:
        dataset = EvaluationDataset(name="identity-safe-loader", dataset_type="fixture")
        db.add(dataset)
        await db.flush()
        example = EvaluationExample(dataset_id=dataset.id, **_values("gold-1", "before"))
        db.add(example)
        await db.commit()
        original_id = example.id

        await _upsert_examples(db, dataset, [_values("gold-1", "after")])
        await db.commit()

        persisted = (
            await db.execute(
                select(EvaluationExample).where(EvaluationExample.dataset_id == dataset.id)
            )
        ).scalar_one()
        assert persisted.id == original_id
        assert persisted.input_data["exact_quote"] == "after"
