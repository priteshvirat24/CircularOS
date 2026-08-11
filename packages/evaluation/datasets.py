"""Load the hand-annotated gold set into the evaluation tables.

Reads ``data/goldsets/obligations.jsonl`` and ``data/goldsets/changeset.jsonl``
(produced + validated by ``scripts/build_goldset.py`` / ``scripts/validate_goldset.py``)
and materializes them as ``EvaluationDataset`` + ``EvaluationExample`` rows that the
Phase-4 eval runner will score against.

Idempotent: each dataset is keyed by a stable name and each example by its ``gold_id``.
Reloads update examples in place so historical ``EvaluationResult`` foreign keys remain
valid. Removing a previously loaded gold ID is refused; that requires a versioned dataset.

Usage:
    python -m packages.evaluation.datasets            # load both gold sets
    python -m packages.evaluation.datasets --check     # report counts, don't write
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import async_session_maker
from packages.regulatory_core.models.documents import RegulatoryDocument
from packages.regulatory_core.models.evaluation import (
    EvaluationDataset,
    EvaluationExample,
)

OBLIGATIONS_JSONL = "data/goldsets/obligations.jsonl"
CHANGESET_JSONL = "data/goldsets/changeset.jsonl"

OBLIGATION_DATASET = "SEBI Stockbroker Obligations Gold Set (Aug-2024)"
CHANGE_DATASET = "SEBI Stockbroker Change-Set (Aug-2024 -> Jun-2025)"
AUG_DOC_TITLE = "stockbrokers_master_2024-08-09.pdf"

_OBL_EXPECTED_FIELDS = (
    "is_obligation",
    "normalized_obligation",
    "actor",
    "action",
    "object",
    "conditions",
    "exceptions",
    "frequency",
    "deadline",
    "evidence_requirement",
    "penalty_reference",
)


def _load_jsonl(path: str) -> list[dict[str, Any]]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


async def _upsert_dataset(
    db: AsyncSession,
    name: str,
    dataset_type: str,
    description: str,
    metadata: dict[str, Any],
) -> EvaluationDataset:
    """Get or update a dataset by its stable name without replacing example identities."""
    ds = (
        await db.execute(select(EvaluationDataset).where(EvaluationDataset.name == name))
    ).scalar_one_or_none()
    if ds is None:
        ds = EvaluationDataset(
            name=name,
            dataset_type=dataset_type,
            description=description,
            metadata_json=metadata,
            is_active=True,
        )
        db.add(ds)
        await db.flush()
    else:
        ds.dataset_type = dataset_type
        ds.description = description
        ds.metadata_json = metadata
    return ds


async def _upsert_examples(
    db: AsyncSession,
    dataset: EvaluationDataset,
    desired: list[dict[str, Any]],
) -> None:
    """Synchronize examples by gold ID while preserving IDs referenced by prior results."""
    existing = list(
        (
            await db.execute(
                select(EvaluationExample).where(EvaluationExample.dataset_id == dataset.id)
            )
        ).scalars()
    )
    by_gold_id: dict[str, EvaluationExample] = {}
    for example in existing:
        gold_id = str((example.input_data or {}).get("gold_id", ""))
        if not gold_id or gold_id in by_gold_id:
            raise ValueError(
                f"Dataset {dataset.name!r} has missing or duplicate persisted gold IDs"
            )
        by_gold_id[gold_id] = example

    desired_ids = {str(item["input_data"]["gold_id"]) for item in desired}
    removed = sorted(set(by_gold_id) - desired_ids)
    if removed:
        raise ValueError(
            f"Refusing to remove {len(removed)} gold examples from {dataset.name!r}; "
            "create a versioned dataset instead. IDs: " + ", ".join(removed[:10])
        )

    for values in desired:
        gold_id = str(values["input_data"]["gold_id"])
        persisted = by_gold_id.get(gold_id)
        if persisted is None:
            db.add(EvaluationExample(dataset_id=dataset.id, **values))
            continue
        for field, value in values.items():
            setattr(persisted, field, value)


async def load_goldsets(check_only: bool = False) -> dict[str, Any]:
    obligations = _load_jsonl(OBLIGATIONS_JSONL)
    changes = _load_jsonl(CHANGESET_JSONL)

    async with async_session_maker() as db:
        # Link obligation examples to the ingested Aug-2024 document, if present.
        aug_doc_id = (
            await db.execute(
                select(RegulatoryDocument.id).where(RegulatoryDocument.title == AUG_DOC_TITLE)
            )
        ).scalar_one_or_none()

        if check_only:
            counts = {}
            for name in (OBLIGATION_DATASET, CHANGE_DATASET):
                ds = (
                    await db.execute(
                        select(EvaluationDataset).where(EvaluationDataset.name == name)
                    )
                ).scalar_one_or_none()
                n = 0
                if ds is not None:
                    n = (
                        await db.execute(
                            select(func.count())
                            .select_from(EvaluationExample)
                            .where(EvaluationExample.dataset_id == ds.id)
                        )
                    ).scalar() or 0
                counts[name] = n
            return {
                "jsonl_obligations": len(obligations),
                "jsonl_changes": len(changes),
                "db_counts": counts,
                "aug_doc_linked": aug_doc_id is not None,
            }

        # ── obligations dataset ─────────────────────────────────────────
        pos = sum(1 for r in obligations if r.get("is_obligation"))
        obl_meta = {
            "source_document": "stockbrokers_master_2024-08-09",
            "total": len(obligations),
            "positive": pos,
            "negative": len(obligations) - pos,
            "verification_status": "AI-first-pass; human verification pending",
            "provenance": "every exact_quote validated as a verbatim substring of the real Aug-2024 PDF",
        }
        obl_ds = await _upsert_dataset(
            db,
            OBLIGATION_DATASET,
            "obligation_extraction",
            "Hand-annotated obligation gold set from the real Aug-2024 SEBI stockbroker "
            "master circular, including negative (definitional/informational) examples.",
            obl_meta,
        )
        obligation_examples = []
        for r in obligations:
            src = r["source"]
            expected = {k: r.get(k) for k in _OBL_EXPECTED_FIELDS}
            obligation_examples.append(
                {
                    "input_data": {
                        "gold_id": r["id"],
                        "document": src["document"],
                        "clause_ref": src["clause_ref"],
                        "exact_quote": src["exact_quote"],
                    },
                    "expected_output": expected,
                    "source_document_id": aug_doc_id,
                    "difficulty": r.get("difficulty"),
                    "tags": r.get("tags") or [],
                    "annotator_notes": r.get("annotator_notes"),
                }
            )
        await _upsert_examples(db, obl_ds, obligation_examples)
        obl_ds.example_count = len(obligations)

        # ── change-set dataset ──────────────────────────────────────────
        from collections import Counter

        ctypes = Counter(r["change_type"] for r in changes)
        chg_meta = {
            "old_document": "stockbrokers_master_2024-08-09",
            "new_document": "stockbrokers_master_2025-06-17",
            "total": len(changes),
            "by_type": dict(ctypes),
            "verification_status": "AI-first-pass; human verification pending",
            "provenance": "old_text validated against Aug-2024 PDF; new_text against Jun-2025 PDF",
        }
        chg_ds = await _upsert_dataset(
            db,
            CHANGE_DATASET,
            "diff",
            "Labeled change-set between the Aug-2024 and Jun-2025 SEBI stockbroker master "
            "circulars, including cosmetic renumberings labeled NOT_A_CHANGE.",
            chg_meta,
        )
        change_examples = []
        for r in changes:
            change_examples.append(
                {
                    "input_data": {
                        "gold_id": r["id"],
                        "old_ref": r.get("old_ref"),
                        "new_ref": r.get("new_ref"),
                        "old_text": r.get("old_text"),
                        "new_text": r.get("new_text"),
                        "obligation_summary": r.get("obligation_summary"),
                    },
                    "expected_output": {
                        "change_type": r["change_type"],
                        "changed_fields": r.get("changed_fields") or [],
                        "materiality_expected": r.get("materiality_expected"),
                    },
                    "source_document_id": aug_doc_id,
                    "tags": [r["change_type"]],
                    "annotator_notes": r.get("notes"),
                }
            )
        await _upsert_examples(db, chg_ds, change_examples)
        chg_ds.example_count = len(changes)

        await db.commit()

        return {
            "obligations_loaded": len(obligations),
            "changes_loaded": len(changes),
            "obligation_dataset_id": str(obl_ds.id),
            "change_dataset_id": str(chg_ds.id),
            "aug_doc_linked": aug_doc_id is not None,
        }


async def _amain() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="Report counts, don't write.")
    args = ap.parse_args()

    for p in (OBLIGATIONS_JSONL, CHANGESET_JSONL):
        if not os.path.exists(p):
            print(f"ERROR: missing {p} — run scripts/build_goldset.py first.")
            return 2

    result = await load_goldsets(check_only=args.check)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_amain()))
