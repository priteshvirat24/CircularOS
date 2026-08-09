"""Load the hand-annotated gold set into the evaluation tables.

Reads ``data/goldsets/obligations.jsonl`` and ``data/goldsets/changeset.jsonl``
(produced + validated by ``scripts/build_goldset.py`` / ``scripts/validate_goldset.py``)
and materializes them as ``EvaluationDataset`` + ``EvaluationExample`` rows that the
Phase-4 eval runner will score against.

Idempotent: each dataset is keyed by a stable name. On re-run, the dataset's existing
examples are deleted and re-inserted from the JSONL, so running twice yields exactly
one copy — no duplicates.

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

from sqlalchemy import delete, func, select
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
    """Get-or-create a dataset by name, and clear its examples for idempotent reload."""
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
        # Clear prior examples so a reload never duplicates.
        await db.execute(delete(EvaluationExample).where(EvaluationExample.dataset_id == ds.id))
    return ds


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
        for r in obligations:
            src = r["source"]
            expected = {k: r.get(k) for k in _OBL_EXPECTED_FIELDS}
            db.add(
                EvaluationExample(
                    dataset_id=obl_ds.id,
                    input_data={
                        "gold_id": r["id"],
                        "document": src["document"],
                        "clause_ref": src["clause_ref"],
                        "exact_quote": src["exact_quote"],
                    },
                    expected_output=expected,
                    source_document_id=aug_doc_id,
                    difficulty=r.get("difficulty"),
                    tags=r.get("tags") or [],
                    annotator_notes=r.get("annotator_notes"),
                )
            )
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
        for r in changes:
            db.add(
                EvaluationExample(
                    dataset_id=chg_ds.id,
                    input_data={
                        "gold_id": r["id"],
                        "old_ref": r.get("old_ref"),
                        "new_ref": r.get("new_ref"),
                        "old_text": r.get("old_text"),
                        "new_text": r.get("new_text"),
                        "obligation_summary": r.get("obligation_summary"),
                    },
                    expected_output={
                        "change_type": r["change_type"],
                        "changed_fields": r.get("changed_fields") or [],
                        "materiality_expected": r.get("materiality_expected"),
                    },
                    source_document_id=aug_doc_id,
                    tags=[r["change_type"]],
                    annotator_notes=r.get("notes"),
                )
            )
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
