"""Free-tier-aware full extraction for the real Aug-2024 and Jun-2025 circulars.

The PDF parser's clause rows contain rolling/overlapping context, so invoking one model call
per stored clause would duplicate work and exceed free-tier request quotas. This runner uses
the deterministic top-level section spans already used by the diff engine and invokes the
existing structured obligation extractor exactly once per non-empty real section.

Progress is checkpointed in ``ExtractionRun.checkpoint_data`` after every successful section.
The live obligation registry is replaced atomically only when both documents are complete;
an interrupted quota-limited run can therefore resume without publishing a partial corpus.
No gold labels are read or used for selection.

Run from the repository root:

    .venv/bin/python scripts/extract_obligations_full.py
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import fitz  # type: ignore[import-untyped]
import structlog
from langchain_core.callbacks import UsageMetadataCallbackHandler
from sqlalchemy import delete, select

from apps.api.config import get_settings
from apps.api.database import async_session_maker
from packages.ai.prompts import get_prompt
from packages.ai.providers import get_structured_llm
from packages.ai.schemas import ClauseExtractionResult
from packages.ai.workflows.extraction import _sum_usage
from packages.diff_engine.sections import extract_sections
from packages.regulatory_core.models.agents import (
    AgentRun,
    AgentStatus,
    ExtractionRun,
    WorkflowStatus,
)
from packages.regulatory_core.models.documents import (
    Clause,
    ClauseType,
    DocumentStatus,
    RegulatoryDocument,
)
from packages.regulatory_core.models.obligations import (
    Obligation,
    ObligationCitation,
    ObligationStatus,
)

logger = structlog.get_logger()

WORKFLOW_TYPE = "full_section"
PDF_DIR = Path("data/goldsets/circulars")
DOCUMENT_TITLES = (
    "stockbrokers_master_2024-08-09.pdf",
    "stockbrokers_master_2025-06-17.pdf",
)
MAX_KEY_ATTEMPTS = 10
CONCURRENCY = 10


@dataclass(frozen=True)
class SourceSection:
    number: int
    title: str
    body: str
    char_start: int | None
    char_end: int | None


def _load_sections(title: str) -> list[SourceSection]:
    pdf_path = PDF_DIR / title
    with fitz.open(pdf_path) as document:
        text = "\n".join(page.get_text() for page in document)
    return [
        SourceSection(
            number=section.number,
            title=section.title,
            body=section.body,
            char_start=section.char_start,
            char_end=section.char_end,
        )
        for section in extract_sections(text, max_body_chars=10_000_000)
    ]


def _jsonable_result(result: ClauseExtractionResult) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(result.model_dump_json()))


def _checkpoint(run: ExtractionRun) -> dict[str, Any]:
    value = run.checkpoint_data or {}
    return {
        "version": 1,
        "model": get_settings().reasoning_model_name,
        "sections": dict(value.get("sections", {})),
        "errors": list(value.get("errors", [])),
    }


async def _get_or_create_run(document: RegulatoryDocument) -> ExtractionRun:
    async with async_session_maker() as db:
        existing = (
            await db.execute(
                select(ExtractionRun)
                .where(
                    ExtractionRun.document_id == document.id,
                    ExtractionRun.workflow_type == WORKFLOW_TYPE,
                    ExtractionRun.status.in_(
                        [WorkflowStatus.RUNNING, WorkflowStatus.PAUSED, WorkflowStatus.FAILED]
                    ),
                )
                .order_by(ExtractionRun.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.status = WorkflowStatus.RUNNING
            existing.current_stage = "extract_sections"
            existing.error_message = None
            await db.commit()
            return existing

        run = ExtractionRun(
            organization_id=document.organization_id,
            document_id=document.id,
            workflow_type=WORKFLOW_TYPE,
            status=WorkflowStatus.RUNNING,
            current_stage="extract_sections",
            started_at=datetime.now(UTC),
            total_clauses=0,
            total_obligations=0,
            total_tokens=0,
            total_cost_usd=0.0,
            checkpoint_data={
                "version": 1,
                "model": get_settings().reasoning_model_name,
                "sections": {},
                "errors": [],
            },
        )
        db.add(run)
        await db.commit()
        return run


async def _record_section(
    run_id: Any,
    section: SourceSection,
    payload: dict[str, Any],
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: int,
) -> None:
    async with async_session_maker() as db:
        run = await db.get(ExtractionRun, run_id)
        if run is None:
            raise RuntimeError(f"Extraction run disappeared: {run_id}")
        checkpoint = _checkpoint(run)
        checkpoint["sections"][str(section.number)] = {
            "title": section.title,
            "result": payload,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "duration_ms": duration_ms,
        }
        run.checkpoint_data = checkpoint
        run.total_clauses = len(checkpoint["sections"])
        run.total_obligations = sum(
            len(item["result"].get("obligations", [])) for item in checkpoint["sections"].values()
        )
        run.total_tokens = sum(
            item.get("prompt_tokens", 0) + item.get("completion_tokens", 0)
            for item in checkpoint["sections"].values()
        )
        db.add(
            AgentRun(
                extraction_run_id=run.id,
                agent_name="full_section_obligation_extractor",
                agent_type="llm_candidate_generation",
                status=AgentStatus.COMPLETED,
                input_summary={
                    "section_number": section.number,
                    "section_title": section.title,
                    "source_chars": len(section.body),
                },
                output_summary={
                    "obligations": len(payload.get("obligations", [])),
                    "needs_human_review": payload.get("needs_human_review", False),
                },
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_ms=duration_ms,
                model_name=get_settings().reasoning_model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost_usd=0.0,
            )
        )
        await db.commit()


async def _mark_interrupted(run_id: Any, error: Exception) -> None:
    async with async_session_maker() as db:
        run = await db.get(ExtractionRun, run_id)
        if run is None:
            return
        checkpoint = _checkpoint(run)
        checkpoint["errors"].append(
            {"at": datetime.now(UTC).isoformat(), "error": str(error)[:2000]}
        )
        run.checkpoint_data = checkpoint
        run.status = WorkflowStatus.PAUSED
        run.current_stage = "quota_or_provider_interruption"
        run.error_message = str(error)[:4000]
        await db.commit()


def _extract_section(
    section: SourceSection, document_title: str
) -> tuple[dict[str, Any], int, int, int]:
    prompt = get_prompt("obligation_extractor")
    messages = prompt.format_messages(
        document_title=document_title,
        clause_number=str(section.number),
        clause_heading=section.title,
        text_content=section.body,
    )
    errors: list[str] = []
    for attempt in range(1, MAX_KEY_ATTEMPTS + 1):
        usage = UsageMetadataCallbackHandler()
        started = time.monotonic()
        try:
            llm = get_structured_llm(ClauseExtractionResult, routing_type="reasoning")
            result = cast(
                ClauseExtractionResult,
                llm.invoke(messages, config={"callbacks": [usage]}),
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            prompt_tokens, completion_tokens = _sum_usage(usage)
            return (
                _jsonable_result(result),
                prompt_tokens,
                completion_tokens,
                duration_ms,
            )
        except Exception as exc:
            errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
            logger.warning(
                "full_section_extraction_attempt_failed",
                section=section.number,
                attempt=attempt,
                error=str(exc)[:500],
            )
    raise RuntimeError(
        f"Section {section.number} failed across {MAX_KEY_ATTEMPTS} rotated keys: "
        + " | ".join(errors)
    )


async def _extract_document(document: RegulatoryDocument) -> ExtractionRun:
    sections = _load_sections(document.title)
    run = await _get_or_create_run(document)
    checkpoint = _checkpoint(run)
    completed = set(checkpoint["sections"])
    logger.info(
        "full_document_extraction_start",
        document=document.title,
        sections=len(sections),
        resumed=len(completed),
    )

    pending: list[SourceSection] = []
    for section in sections:
        if str(section.number) in completed:
            continue
        if section.body.strip():
            pending.append(section)
        else:
            await _record_section(
                run.id,
                section,
                {"obligations": [], "needs_human_review": False, "review_reason": None},
                0,
                0,
                0,
            )

    for batch_start in range(0, len(pending), CONCURRENCY):
        batch = pending[batch_start : batch_start + CONCURRENCY]
        for section in batch:
            logger.info(
                "full_section_extraction_start",
                document=document.title,
                section=section.number,
                progress=f"{batch_start + batch.index(section) + 1}/{len(pending)}",
                chars=len(section.body),
            )
        results = await asyncio.gather(
            *(asyncio.to_thread(_extract_section, section, document.title) for section in batch),
            return_exceptions=True,
        )
        failures: list[Exception] = []
        for section, result in zip(batch, results, strict=True):
            if isinstance(result, BaseException):
                failures.append(
                    result if isinstance(result, Exception) else RuntimeError(str(result))
                )
                continue
            payload, prompt_tokens, completion_tokens, duration_ms = result
            await _record_section(
                run.id,
                section,
                payload,
                prompt_tokens,
                completion_tokens,
                duration_ms,
            )
        if failures:
            await _mark_interrupted(run.id, failures[0])
            raise failures[0]

    async with async_session_maker() as db:
        refreshed = await db.get(ExtractionRun, run.id)
        if refreshed is None:
            raise RuntimeError(f"Extraction run disappeared: {run.id}")
        refreshed.current_stage = "ready_to_publish"
        await db.commit()
        return refreshed


def _as_json_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()] or None
    text = str(value).strip()
    return [text] if text else None


async def _publish_atomically(
    documents: Sequence[RegulatoryDocument],
    runs: list[ExtractionRun],
) -> dict[str, int]:
    sections_by_title = {title: _load_sections(title) for title in DOCUMENT_TITLES}
    run_by_document = {run.document_id: run for run in runs}
    counts: dict[str, int] = {}

    async with async_session_maker() as db:
        document_ids = [document.id for document in documents]
        old_full_run_ids = (
            (
                await db.execute(
                    select(ExtractionRun.id).where(
                        ExtractionRun.document_id.in_(document_ids),
                        ExtractionRun.workflow_type == WORKFLOW_TYPE,
                        ExtractionRun.id.not_in([run.id for run in runs]),
                    )
                )
            )
            .scalars()
            .all()
        )

        # Review/validation dependencies are intentionally guarded rather than silently erased.
        # The current pre-verification corpus has neither; a future rerun must explicitly archive
        # human decisions before replacing published obligations.
        dependency_counts = (
            (
                await db.execute(
                    select(Obligation.id).where(Obligation.document_id.in_(document_ids))
                )
            )
            .scalars()
            .all()
        )
        if dependency_counts:
            from packages.regulatory_core.models.obligations import ReviewTask, ValidationResult

            reviews = (
                await db.execute(
                    select(ReviewTask.id).where(ReviewTask.obligation_id.in_(dependency_counts))
                )
            ).first()
            validations = (
                await db.execute(
                    select(ValidationResult.id).where(
                        ValidationResult.obligation_id.in_(dependency_counts)
                    )
                )
            ).first()
            if reviews or validations:
                raise RuntimeError(
                    "Refusing to replace obligations that have review or validation history"
                )

        await db.execute(delete(Obligation).where(Obligation.document_id.in_(document_ids)))
        if old_full_run_ids:
            await db.execute(delete(Clause).where(Clause.extraction_run_id.in_(old_full_run_ids)))

        for document in documents:
            run = run_by_document[document.id]
            checkpoint = _checkpoint(run)
            inserted = 0
            for order_index, section in enumerate(sections_by_title[document.title]):
                result = checkpoint["sections"].get(str(section.number))
                if result is None:
                    raise RuntimeError(
                        f"Missing completed section {section.number} for {document.title}"
                    )
                payload = result["result"]
                obligations = payload.get("obligations", [])
                clause = Clause(
                    document_id=document.id,
                    clause_number=f"{section.number}.",
                    clause_type=(
                        ClauseType.OBLIGATION if obligations else ClauseType.CONTEXTUAL_STATEMENT
                    ),
                    level=0,
                    order_index=2_000_000 + order_index,
                    text_content=section.body,
                    heading=f"{section.number}. {section.title}",
                    char_start=section.char_start,
                    char_end=section.char_end,
                    classification_confidence=1.0,
                    extraction_run_id=run.id,
                )
                db.add(clause)
                await db.flush()

                for candidate in obligations:
                    risk_value = str(candidate.get("risk_level", "medium")).lower()
                    from packages.regulatory_core.models.obligations import RiskLevel

                    try:
                        risk_level = RiskLevel(risk_value)
                    except ValueError:
                        risk_level = RiskLevel.MEDIUM
                    obligation = Obligation(
                        organization_id=document.organization_id,
                        document_id=document.id,
                        clause_id=clause.id,
                        source_text=section.body,
                        normalized_obligation=candidate.get("normalized_obligation", ""),
                        actor=candidate.get("actor") or "Unknown",
                        action=candidate.get("action") or "Unknown",
                        object=candidate.get("object"),
                        conditions=_as_json_list(candidate.get("conditions")),
                        exceptions=_as_json_list(candidate.get("exceptions")),
                        frequency=candidate.get("frequency"),
                        deadline_description=candidate.get("deadline_description"),
                        risk_level=risk_level,
                        risk_factors={
                            "model_self_confidence": candidate.get("self_confidence"),
                            "extraction_difficulty": candidate.get("difficulty"),
                        },
                        extraction_method="agentic_full_section",
                        extraction_run_id=run.id,
                        prompt_version="obligation_extractor@1.0-full-section",
                        model=get_settings().reasoning_model_name,
                        citation_coordinates={
                            "section_number": section.number,
                            "section_char_start": section.char_start,
                            "section_char_end": section.char_end,
                        },
                        validation_status="pending",
                        status=ObligationStatus.CANDIDATE,
                        review_status="awaiting_verification",
                    )
                    for citation in candidate.get("citations", []):
                        quote = str(citation.get("exact_quote") or "").strip()
                        if not quote:
                            continue
                        local_start = section.body.find(quote)
                        absolute_start = (
                            section.char_start + local_start
                            if section.char_start is not None and local_start >= 0
                            else None
                        )
                        obligation.citations.append(
                            ObligationCitation(
                                field_name=str(citation.get("field_name") or "unknown")[:100],
                                cited_text=quote,
                                char_start=absolute_start,
                                char_end=(absolute_start + len(quote))
                                if absolute_start is not None
                                else None,
                                clause_id=clause.id,
                            )
                        )
                    db.add(obligation)
                    inserted += 1

            run_db = await db.get(ExtractionRun, run.id)
            if run_db is None:
                raise RuntimeError(f"Extraction run disappeared: {run.id}")
            run_db.status = WorkflowStatus.COMPLETED
            run_db.current_stage = "published_pending_verification"
            run_db.completed_at = datetime.now(UTC)
            if run_db.started_at:
                run_db.duration_seconds = (run_db.completed_at - run_db.started_at).total_seconds()
            run_db.total_clauses = len(sections_by_title[document.title])
            run_db.total_obligations = inserted
            run_db.approved_obligations = 0
            run_db.rejected_obligations = 0
            run_db.review_pending = inserted
            document.status = DocumentStatus.PROCESSED
            document.processing_error = None
            counts[document.title] = inserted

        await db.commit()
    return counts


async def main() -> int:
    async with async_session_maker() as db:
        documents = (
            (
                await db.execute(
                    select(RegulatoryDocument)
                    .where(RegulatoryDocument.title.in_(DOCUMENT_TITLES))
                    .order_by(RegulatoryDocument.title)
                )
            )
            .scalars()
            .all()
        )
    if [document.title for document in documents] != list(DOCUMENT_TITLES):
        raise RuntimeError("Both real circular documents must be present in the database")

    runs: list[ExtractionRun] = []
    for document in documents:
        runs.append(await _extract_document(document))

    counts = await _publish_atomically(documents, runs)
    for title, count in counts.items():
        print(f"{title}: {count} obligations published pending verification", flush=True)
    print("FULL BOTH-SIDES EXTRACTION COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
