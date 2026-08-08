"""Regulatory diff service — the async logic shared by the API route and the Celery task.

Deterministic sequence over two documents: read both documents' page text from the DB, run the
pure four-level diff engine, and persist a ``DiffRun`` plus one ``RegulatoryChange`` per detected
change (material rows carry ``requires_confirmation=True``). No Celery import here, so the API
process can call it directly without pulling the worker stack.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import async_session_maker
from packages.diff_engine import run_diff_pipeline
from packages.diff_engine.sections import assign_to_sections, extract_sections
from packages.diff_engine.types import ChangeRow, DiffResult
from packages.policy_engine.changes import ObligationFields
from packages.regulatory_core.models.documents import DocumentPage, RegulatoryDocument
from packages.regulatory_core.models.obligations import (
    ChangeType,
    DiffRun,
    DiffRunStatus,
    MaterialityLevel,
    Obligation,
    RegulatoryChange,
)

logger = structlog.get_logger()


async def _load_document_text(db: AsyncSession, document_id: uuid.UUID) -> str:
    """Reconstruct a document's full text from its stored pages (ordered by page number)."""
    rows = (
        await db.execute(
            select(DocumentPage.text_content)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
    ).all()
    return "\n".join(r[0] for r in rows if r[0])


def _obligation_fields(o: Obligation) -> ObligationFields:
    """Build the pure, comparable ObligationFields from a persisted Obligation row."""
    raw_evidence = o.evidence_requirements
    evidence: str | None
    if isinstance(raw_evidence, list):
        evidence = "; ".join(str(x) for x in raw_evidence) or None
    else:
        evidence = raw_evidence
    return ObligationFields(
        normalized_obligation=o.normalized_obligation or "",
        actor=o.actor,
        action=o.action,
        object=o.object,
        conditions=tuple(o.conditions or ()),
        exceptions=tuple(o.exceptions or ()),
        frequency=o.frequency,
        deadline=o.deadline_description,
        evidence_requirement=evidence,
        penalty_reference=o.penalty_reference,
        applicability=tuple(o.applicability or ()),
        risk_level=o.risk_level.value if o.risk_level else None,
    )


async def _load_obligation_map(
    db: AsyncSession, document_id: uuid.UUID, doc_text: str
) -> dict[int, list[ObligationFields]]:
    """Map a document's extracted obligations to their top-level section number.

    Uses text containment (each obligation's source clause text located within a section body),
    which is robust to the parser's lossy clause numbering. Empty when nothing is extracted yet.
    """
    obls = (
        await db.execute(select(Obligation).where(Obligation.document_id == document_id))
    ).scalars().all()
    if not obls:
        return {}
    sections = extract_sections(doc_text, max_body_chars=20000)
    items: list[tuple[str, object]] = [(o.source_text or "", _obligation_fields(o)) for o in obls]
    raw = assign_to_sections(sections, items)
    return {num: [x for x in payloads if isinstance(x, ObligationFields)]
            for num, payloads in raw.items()}


def change_row_to_model(
    row: ChangeRow,
    diff_run_id: uuid.UUID,
    old_document_id: uuid.UUID,
    new_document_id: uuid.UUID,
) -> RegulatoryChange:
    return RegulatoryChange(
        diff_run_id=diff_run_id,
        old_document_id=old_document_id,
        new_document_id=new_document_id,
        change_type=ChangeType(row.change_type),
        description=row.description or row.obligation,
        old_text=row.old_text,
        new_text=row.new_text,
        changed_fields=row.changed_fields,
        similarity_score=row.similarity_score,
        materiality=MaterialityLevel(row.materiality.value),
        materiality_reasons=row.materiality_reasons,
        requires_confirmation=row.requires_confirmation,
        confidence=row.confidence,
        review_status="pending" if row.requires_confirmation else "auto",
        verification_status="deterministic",
        diff_details={
            "obligation": row.obligation,
            "old_ref": row.old_ref,
            "new_ref": row.new_ref,
            "citations": row.citations,
        },
    )


async def run_diff_async(
    old_document_id: str,
    new_document_id: str,
    created_by: str | None = None,
) -> str:
    """Execute the diff engine on two documents and persist the results. Returns diff_run_id."""
    old_id = uuid.UUID(old_document_id)
    new_id = uuid.UUID(new_document_id)

    async with async_session_maker() as db:
        old_doc = await db.get(RegulatoryDocument, old_id)
        new_doc = await db.get(RegulatoryDocument, new_id)
        if old_doc is None or new_doc is None:
            raise ValueError("both old and new documents must exist")

        run = DiffRun(
            old_document_id=old_id,
            new_document_id=new_id,
            status=DiffRunStatus.RUNNING,
            started_at=datetime.now(UTC),
            created_by=uuid.UUID(created_by) if created_by else None,
        )
        db.add(run)
        await db.flush()

        try:
            old_text = await _load_document_text(db, old_id)
            new_text = await _load_document_text(db, new_id)
            if not old_text or not new_text:
                raise ValueError("one or both documents have no extracted page text")

            # Extracted obligations (when present on both sides) drive the L4 field-level compare;
            # absent, the engine falls back to section-title comparison. Either way is deterministic.
            old_obl_map = await _load_obligation_map(db, old_id, old_text)
            new_obl_map = await _load_obligation_map(db, new_id, new_text)

            result: DiffResult = run_diff_pipeline(
                old_text, new_text,
                old_obligations=old_obl_map,
                new_obligations=new_obl_map,
            )

            for row in result.changes:
                db.add(change_row_to_model(row, run.id, old_id, new_id))

            run.status = DiffRunStatus.COMPLETED
            run.completed_at = datetime.now(UTC)
            run.summary = result.summary
            run.matcher_config = result.matcher
            run.notes = result.notes
            await db.commit()
            logger.info(
                "diff_run_completed",
                diff_run_id=str(run.id),
                **result.summary,
                sections_old=result.old_section_count,
                sections_new=result.new_section_count,
            )
            return str(run.id)

        except Exception as exc:  # noqa: BLE001 — persist failure state, then re-raise
            logger.exception("diff_run_failed", diff_run_id=str(run.id))
            run.status = DiffRunStatus.FAILED
            run.error_message = str(exc)
            run.completed_at = datetime.now(UTC)
            await db.commit()
            raise
