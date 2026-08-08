"""Bounded obligation extraction for both circulars (populates both sides of the diff).

Runs the real extraction graph on a bounded, obligation-dense clause slice per document, and
deliberately includes the clauses of the change-relevant top-level sections (so the diff's
obligation-level L4 has data on the MODIFIED/CREATED sections). Deterministic selection; the
LLM only proposes obligations. Intended to run in the background (several minutes).

    FAST_MODEL_PROVIDER=gemini FAST_MODEL_NAME=gemini-flash-latest \
    REASONING_MODEL_PROVIDER=gemini REASONING_MODEL_NAME=gemini-flash-latest \
    python scripts/extract_obligations_slice.py

Reports the real obligation count per document — whatever it is.
"""

from __future__ import annotations

import asyncio

import fitz
from sqlalchemy import select

from apps.api.database import async_session_maker
from apps.worker.tasks.extraction import run_extraction_workflow_async
from packages.diff_engine.sections import extract_sections
from packages.regulatory_core.models.documents import Clause, RegulatoryDocument
from packages.regulatory_core.models.obligations import Obligation

# doc title → PDF path (to recover clean section bodies) and the change-relevant sections.
DOCS = {
    "stockbrokers_master_2024-08-09.pdf": {
        "pdf": "data/goldsets/circulars/stockbrokers_master_2024-08-09.pdf",
        "sections": [31],  # the old side of the MODIFIED
    },
    "stockbrokers_master_2025-06-17.pdf": {
        "pdf": "data/goldsets/circulars/stockbrokers_master_2025-06-17.pdf",
        "sections": [17, 32, 71, 72, 88],  # new side of MODIFIED + the CREATED sections
    },
}
CAP = 30  # bound LLM cost per document


def _full_text(pdf: str) -> str:
    d = fitz.open(pdf)
    t = "\n".join(pg.get_text() for pg in d)
    d.close()
    return t


def _select_clause_ids(clauses, section_bodies: list[str]) -> list:
    """Prefer clauses whose text falls inside a target section body, then obligation-dense fill."""
    joined = "\n".join(section_bodies)
    in_target, fill = [], []
    for cid, txt in clauses:
        if not txt:
            continue
        probe = txt.strip()[:80]
        if probe and probe in joined:
            in_target.append(cid)
        elif " shall " in txt and 150 < len(txt) < 1500:
            fill.append(cid)
    picked = in_target[:CAP]
    for cid in fill:
        if len(picked) >= CAP:
            break
        picked.append(cid)
    return picked


async def main() -> int:
    for title, cfg in DOCS.items():
        async with async_session_maker() as db:
            doc = (
                await db.execute(
                    select(RegulatoryDocument).where(RegulatoryDocument.title == title)
                )
            ).scalar_one()
            clauses = (
                await db.execute(
                    select(Clause.id, Clause.text_content)
                    .where(Clause.document_id == doc.id)
                    .order_by(Clause.order_index)
                )
            ).all()

        secs = {s.number: s for s in extract_sections(_full_text(cfg["pdf"]))}
        bodies = [secs[n].body for n in cfg["sections"] if n in secs and secs[n].body]
        picks = _select_clause_ids(clauses, bodies)
        print(f"[{title}] extracting {len(picks)} clauses "
              f"(target sections {cfg['sections']}) ...", flush=True)

        await run_extraction_workflow_async(str(doc.id), clause_ids=picks)

        async with async_session_maker() as db:
            n = (
                await db.execute(
                    select(Obligation).where(Obligation.document_id == doc.id)
                )
            ).scalars().all()
            print(f"[{title}] obligations now: {len(n)}", flush=True)

    print("EXTRACTION SLICE COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
