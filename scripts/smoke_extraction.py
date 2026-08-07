"""Phase 0 smoke test: ingest a real SEBI PDF and run the real extraction graph.

Proves the core engine end-to-end on real API keys:
  parse PDF -> persist RegulatoryDocument/DocumentPage/Clause rows ->
  run the extraction LangGraph -> persist Obligation rows with citations.

Usage:
    python scripts/smoke_extraction.py path/to/circular.pdf [--max-clauses N]

The ingestion here mirrors ``apps/worker/tasks/document.py::process_document_async``
but runs inline (no Celery), so the smoke is self-contained. Extraction reuses
the real ``run_extraction_workflow_async`` unchanged.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import uuid

from sqlalchemy import func, select

from apps.api.config import get_settings
from apps.api.database import async_session_maker
from packages.document_processing.parser import parse_pdf, reconstruct_clause_hierarchy
from packages.regulatory_core.models.documents import (
    Clause,
    DocumentPage,
    DocumentStatus,
    RegulatoryDocument,
)
from packages.regulatory_core.models.obligations import Obligation
from apps.worker.tasks.extraction import run_extraction_workflow_async


async def ingest_pdf(path: str, max_clauses: int | None) -> str:
    """Parse a PDF and persist document, pages, and clauses. Returns document id."""
    with open(path, "rb") as f:
        content = f.read()
    sha256 = hashlib.sha256(content).hexdigest()

    async with async_session_maker() as db:
        existing = await db.execute(
            select(RegulatoryDocument).where(RegulatoryDocument.sha256_hash == sha256)
        )
        doc = existing.scalar_one_or_none()
        if doc is not None:
            print(f"  document already ingested (sha256={sha256[:12]}...), reusing {doc.id}")
            return str(doc.id)

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
        if max_clauses is not None:
            clauses = clauses[:max_clauses]
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
            f"  ingested: {parsed.page_count} pages, {len(clauses)} clauses "
            f"(quality={parsed.quality_score})"
        )
        return str(doc.id)


async def report(document_id: str) -> int:
    """Print obligation count and one obligation with its citations. Returns count."""
    async with async_session_maker() as db:
        total = (
            await db.execute(
                select(func.count())
                .select_from(Obligation)
                .where(Obligation.document_id == uuid.UUID(document_id))
            )
        ).scalar() or 0
        print(f"\n  Obligation rows written for this document: {total}")

        result = await db.execute(
            select(Obligation)
            .where(Obligation.document_id == uuid.UUID(document_id))
            .order_by(Obligation.created_at)
            .limit(1)
        )
        obl = result.scalars().first()
        if obl is None:
            return total

        print("\n  --- First obligation ---")
        print(f"  id:          {obl.id}")
        print(f"  actor:       {obl.actor}")
        print(f"  action:      {obl.action}")
        print(f"  normalized:  {obl.normalized_obligation}")
        print(f"  risk_level:  {obl.risk_level.value if obl.risk_level else None}")
        print(f"  status:      {obl.status.value}")
        print(f"  model:       {obl.model}")
        print(f"  citations:   {len(obl.citations)}")
        for cit in obl.citations:
            snippet = cit.cited_text[:160].replace("\n", " ")
            print(f'    - [{cit.field_name}] "{snippet}"')
        return total


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="Path to a real SEBI PDF")
    parser.add_argument(
        "--max-clauses",
        type=int,
        default=40,
        help="Cap clauses sent through extraction to bound LLM cost (default 40)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"ERROR: file not found: {args.pdf}")
        return 2

    settings = get_settings()
    if not settings.gemini_api_key:
        print(
            "ERROR: GEMINI_API_KEY is not set in .env. Fill it in before running the "
            "smoke test (the extraction graph routes fast+reasoning to Gemini)."
        )
        return 3

    print(f"[1/3] Ingesting {args.pdf} ...")
    document_id = await ingest_pdf(args.pdf, args.max_clauses)

    print(f"[2/3] Running real extraction graph on document {document_id} ...")
    await run_extraction_workflow_async(document_id)

    print("[3/3] Verifying persisted obligations ...")
    total = await report(document_id)

    if total >= 1:
        print("\nSMOKE PASS: the real extraction graph wrote >= 1 Obligation row.")
        return 0
    print("\nSMOKE FAIL: no obligations were written. Check logs above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
