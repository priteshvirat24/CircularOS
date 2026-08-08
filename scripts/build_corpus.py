"""Phase 1 corpus builder.

Ingests the real SEBI stockbroker master-circular pair into the DB through the
real document pipeline, then runs the real extraction graph on an obligation-dense
slice of the Aug-2024 circular.

Why a *slice* for extraction: the master circular is ~1200 clauses. The graph's
clause-classification pass makes one fast-model call per clause; running it over
the whole document would exceed the free-tier daily request cap. Ingestion still
persists every clause (so the document is complete in the DB and satisfies the
"≥100 clauses" gate); only the LLM extraction is bounded to a dense subset large
enough to clear the "≥100 obligations" gate honestly.

Usage:
    python scripts/build_corpus.py                 # ingest both + extract slice
    python scripts/build_corpus.py --ingest-only   # ingest both, no LLM calls
    python scripts/build_corpus.py --max-extract N  # cap clauses sent to the graph

Idempotent: documents are keyed by SHA-256; re-running reuses existing rows.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import re
import uuid

from sqlalchemy import func, select

from apps.api.config import get_settings
from apps.api.database import async_session_maker
from apps.worker.tasks.extraction import run_extraction_workflow_async
from packages.document_processing.parser import parse_pdf, reconstruct_clause_hierarchy
from packages.regulatory_core.models.documents import (
    Clause,
    DocumentPage,
    DocumentStatus,
    RegulatoryDocument,
)
from packages.regulatory_core.models.obligations import Obligation

CIRCULARS = {
    "aug2024": "data/goldsets/circulars/stockbrokers_master_2024-08-09.pdf",
    "jun2025": "data/goldsets/circulars/stockbrokers_master_2025-06-17.pdf",
}

# Cue words that mark a clause as likely carrying a mandatory obligation.
_OBLIGATION_CUES = re.compile(
    r"\b(shall|must|required to|shall not|are required|is required|"
    r"shall ensure|shall maintain|shall submit|shall report|shall not)\b",
    re.IGNORECASE,
)


async def ingest_full(path: str) -> str:
    """Parse a PDF and persist document + pages + ALL clauses. Idempotent by SHA-256.

    Returns the document id.
    """
    with open(path, "rb") as f:
        content = f.read()
    sha256 = hashlib.sha256(content).hexdigest()

    async with async_session_maker() as db:
        existing = (
            await db.execute(
                select(RegulatoryDocument).where(
                    RegulatoryDocument.sha256_hash == sha256
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            n = (
                await db.execute(
                    select(func.count())
                    .select_from(Clause)
                    .where(Clause.document_id == existing.id)
                )
            ).scalar() or 0
            print(f"  reuse {os.path.basename(path)} (sha {sha256[:12]}…) — {n} clauses")
            return str(existing.id)

        doc = RegulatoryDocument(
            title=os.path.basename(path),
            file_path=os.path.abspath(path),
            file_size_bytes=len(content),
            mime_type="application/pdf",
            sha256_hash=sha256,
            status=DocumentStatus.PROCESSING,
        )
        db.add(doc)
        await db.flush()

        print(f"  parsing {os.path.basename(path)} … (table detection is slow on 400+ pages)")
        parsed = parse_pdf(doc.file_path)
        doc.page_count = parsed.page_count
        doc.parsing_quality_score = parsed.quality_score
        doc.ocr_applied = parsed.needs_ocr

        for page in parsed.pages:
            db.add(
                DocumentPage(
                    document_id=doc.id,
                    page_number=page.page_number,
                    text_content=page.text_content,
                    has_tables=page.has_tables,
                    has_images=page.has_images,
                    word_count=page.word_count,
                    tables_json=page.tables if page.tables else None,
                )
            )

        clauses = reconstruct_clause_hierarchy(parsed.headings, parsed.pages)
        for c in clauses:
            db.add(
                Clause(
                    document_id=doc.id,
                    clause_number=c["clause_number"],
                    heading=c["heading"],
                    text_content=c["text_content"],
                    level=c["level"],
                    page_start=c["page_start"],
                    page_end=c["page_end"],
                    order_index=c["order_index"],
                )
            )

        doc.status = DocumentStatus.STRUCTURED
        await db.commit()
        print(
            f"  ingested {os.path.basename(path)}: {parsed.page_count} pages, "
            f"{len(clauses)} clauses, quality={parsed.quality_score}"
        )
        return str(doc.id)


async def select_dense_clauses(document_id: str, max_clauses: int) -> list[uuid.UUID]:
    """Pick obligation-dense clauses to send through the extraction graph.

    Heuristic: clauses carrying obligation cue words with enough substance
    (>150 chars), taken in document order and capped. Deterministic.
    """
    async with async_session_maker() as db:
        rows = (
            await db.execute(
                select(Clause)
                .where(Clause.document_id == uuid.UUID(document_id))
                .order_by(Clause.order_index)
            )
        ).scalars().all()

    # Rank obligation-bearing clauses by cue density (more "shall/must/..." hits =
    # more obligations per LLM call) so a bounded budget yields the most obligations.
    scored: list[tuple[int, int, uuid.UUID]] = []
    for c in rows:
        text = c.text_content or ""
        if len(text) < 150:
            continue
        hits = len(_OBLIGATION_CUES.findall(text))
        if hits == 0:
            continue
        scored.append((hits, c.order_index, c.id))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [cid for _, _, cid in scored[:max_clauses]]


async def report_obligations(document_id: str) -> int:
    async with async_session_maker() as db:
        total = (
            await db.execute(
                select(func.count())
                .select_from(Obligation)
                .where(Obligation.document_id == uuid.UUID(document_id))
            )
        ).scalar() or 0
    return total


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest-only", action="store_true", help="Ingest both PDFs, no LLM.")
    ap.add_argument(
        "--max-extract",
        type=int,
        default=110,
        help="Max obligation-dense clauses sent through the graph (default 110).",
    )
    args = ap.parse_args()

    for path in CIRCULARS.values():
        if not os.path.exists(path):
            print(f"ERROR: missing corpus file: {path}")
            return 2

    print("[1/3] Ingesting both circulars (full clause trees) …")
    doc_ids = {tag: await ingest_full(path) for tag, path in CIRCULARS.items()}

    if args.ingest_only:
        print("\n--ingest-only: skipping extraction.")
        return 0

    settings = get_settings()
    if not (settings.gemini_api_key or settings.groq_api_key):
        print("ERROR: need GEMINI_API_KEY and/or GROQ_API_KEY for extraction.")
        return 3

    aug_id = doc_ids["aug2024"]
    print(f"\n[2/3] Selecting up to {args.max_extract} obligation-dense clauses from Aug-2024 …")
    clause_ids = await select_dense_clauses(aug_id, args.max_extract)
    print(f"  selected {len(clause_ids)} clauses for extraction")

    print("[3/3] Running the real extraction graph on the slice (rate-limited; be patient) …")
    await run_extraction_workflow_async(aug_id, clause_ids=clause_ids)

    total = await report_obligations(aug_id)
    print(f"\n  Obligation rows on Aug-2024: {total}")
    if total >= 100:
        print("  PASS: extraction produced ≥ 100 obligations.")
        return 0
    print("  Below 100 — re-run with a larger --max-extract or check quota above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
