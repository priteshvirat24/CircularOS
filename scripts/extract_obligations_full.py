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
import hashlib
import json
import re
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import fitz  # type: ignore[import-untyped]
import structlog
from langchain_core.callbacks import UsageMetadataCallbackHandler
from sqlalchemy import select

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
MAX_ATTEMPTS = 6
CONCURRENCY = 4
REQUEST_START_INTERVAL_SECONDS = 16.0
RUN_CONFIG_VERSION = 7
PROMPT_VERSION = "obligation_extractor@1.1-full-section-chunked"
SCHEMA_VERSION = "ClauseExtractionResult@1"
MAX_CHUNK_CHARS = 12_000
CHUNKING_VERSION = "line-boundary-nonoverlap-v1"
SECTION_LOCATOR_VERSION = "toc-title-aligned-body-region-v4"
RATE_LIMIT_SOURCE = (
    "Observed Phase 4.5 probes: four requests were accepted, the fifth returned Mistral "
    "rate_limited code 1300, and a new request 42 seconds later still returned 1300 after "
    "the first four had completed. Treat as a rolling four-requests/minute limit: starts "
    "are spaced 16 seconds apart with at most four calls in flight."
)
_RETRY_AFTER = re.compile(r"retry(?:-after| in)?[^0-9]*([0-9]+(?:\.[0-9]+)?)", re.I)


@dataclass(frozen=True)
class SourceSection:
    number: int
    title: str
    body: str
    char_start: int | None
    char_end: int | None


@dataclass(frozen=True)
class SourceChunk:
    section_number: int
    section_title: str
    chunk_index: int
    chunk_count: int
    body: str
    char_start: int | None
    char_end: int | None

    @property
    def checkpoint_key(self) -> str:
        return f"{self.section_number}:{self.chunk_index}"


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


def _chunk_section(section: SourceSection, max_chars: int = MAX_CHUNK_CHARS) -> list[SourceChunk]:
    """Split at source line boundaries without overlap or text loss."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    text = section.body
    spans: list[tuple[int, int]] = []
    start = 0
    while len(text) - start > max_chars:
        limit = start + max_chars
        cut = text.rfind("\n", start + max_chars // 2, limit + 1)
        cut = limit if cut < 0 else cut + 1
        spans.append((start, cut))
        start = cut
    spans.append((start, len(text)))
    count = len(spans)
    return [
        SourceChunk(
            section_number=section.number,
            section_title=section.title,
            chunk_index=index,
            chunk_count=count,
            body=text[local_start:local_end],
            char_start=(section.char_start + local_start)
            if section.char_start is not None
            else None,
            char_end=(section.char_start + local_end) if section.char_start is not None else None,
        )
        for index, (local_start, local_end) in enumerate(spans)
    ]


def _load_chunks(title: str) -> list[SourceChunk]:
    return [chunk for section in _load_sections(title) for chunk in _chunk_section(section)]


def _jsonable_result(result: ClauseExtractionResult) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(result.model_dump_json()))


def _run_config() -> dict[str, Any]:
    settings = get_settings()
    provider = settings.reasoning_model_provider
    model = settings.reasoning_model_name
    if provider != "mistral" or model != "mistral-large-latest":
        raise RuntimeError(
            "Full-corpus Phase 4.5 extraction requires "
            "mistral/mistral-large-latest for both documents"
        )
    payload = {
        "version": RUN_CONFIG_VERSION,
        "provider": provider,
        "model": model,
        "temperature": 0.0,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "chunking_version": CHUNKING_VERSION,
        "section_locator_version": SECTION_LOCATOR_VERSION,
        "max_chunk_chars": MAX_CHUNK_CHARS,
        "concurrency": CONCURRENCY,
        "request_start_interval_seconds": REQUEST_START_INTERVAL_SECONDS,
        "rate_limit_source": RATE_LIMIT_SOURCE,
        "cost_policy": "Mistral Experiment free tier; persisted cost USD 0.00",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {**payload, "hash": hashlib.sha256(canonical.encode()).hexdigest()}


def _checkpoint(run: ExtractionRun) -> dict[str, Any]:
    value = run.checkpoint_data or {}
    return {
        "version": value.get("version", RUN_CONFIG_VERSION),
        "corpus_run_id": value.get("corpus_run_id"),
        "run_config": dict(value.get("run_config", {})),
        "run_config_hash": value.get("run_config_hash"),
        "provider": value.get("provider"),
        "model": value.get("model"),
        "sections": dict(value.get("sections", {})),
        "errors": list(value.get("errors", [])),
    }


def assert_consistent_run_provenance(runs: Sequence[ExtractionRun]) -> dict[str, str]:
    """Refuse mixed providers, models, configs, or corpus batch identities."""
    if len(runs) != len(DOCUMENT_TITLES):
        raise RuntimeError(f"Expected {len(DOCUMENT_TITLES)} document runs, got {len(runs)}")
    checkpoints = [_checkpoint(run) for run in runs]
    required = ("corpus_run_id", "run_config_hash", "provider", "model")
    for field in required:
        values = {str(checkpoint.get(field) or "") for checkpoint in checkpoints}
        if "" in values or len(values) != 1:
            raise RuntimeError(f"Mixed or missing full-corpus provenance field: {field}")
    return {field: str(checkpoints[0][field]) for field in required}


async def _resolve_corpus_run_id(
    documents: Sequence[RegulatoryDocument], run_config: dict[str, Any]
) -> str:
    """Resume one compatible corpus batch or create a new shared identity."""
    async with async_session_maker() as db:
        candidates = list(
            (
                await db.execute(
                    select(ExtractionRun)
                    .where(
                        ExtractionRun.document_id.in_([document.id for document in documents]),
                        ExtractionRun.workflow_type == WORKFLOW_TYPE,
                        ExtractionRun.status.in_(
                            [WorkflowStatus.RUNNING, WorkflowStatus.PAUSED, WorkflowStatus.FAILED]
                        ),
                    )
                    .order_by(ExtractionRun.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
    compatible = [
        _checkpoint(run)
        for run in candidates
        if _checkpoint(run).get("run_config_hash") == run_config["hash"]
    ]
    corpus_ids = {str(item.get("corpus_run_id") or "") for item in compatible}
    corpus_ids.discard("")
    if len(corpus_ids) > 1:
        raise RuntimeError("Multiple compatible incomplete corpus batches exist; reconcile first")
    return next(iter(corpus_ids), str(uuid.uuid4()))


async def _get_or_create_run(
    document: RegulatoryDocument, corpus_run_id: str, run_config: dict[str, Any]
) -> ExtractionRun:
    async with async_session_maker() as db:
        candidates = list(
            (
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
                )
            )
            .scalars()
            .all()
        )
        existing = next(
            (
                run
                for run in candidates
                if _checkpoint(run).get("corpus_run_id") == corpus_run_id
                and _checkpoint(run).get("run_config_hash") == run_config["hash"]
            ),
            None,
        )
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
                "version": RUN_CONFIG_VERSION,
                "corpus_run_id": corpus_run_id,
                "run_config": run_config,
                "run_config_hash": run_config["hash"],
                "provider": run_config["provider"],
                "model": run_config["model"],
                "sections": {},
                "errors": [],
            },
        )
        db.add(run)
        await db.commit()
        return run


async def _record_section(
    run_id: Any,
    section: SourceChunk,
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
        checkpoint["sections"][section.checkpoint_key] = {
            "section_number": section.section_number,
            "title": section.section_title,
            "chunk_index": section.chunk_index,
            "chunk_count": section.chunk_count,
            "char_start": section.char_start,
            "char_end": section.char_end,
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
                    "section_number": section.section_number,
                    "section_title": section.section_title,
                    "chunk_index": section.chunk_index,
                    "chunk_count": section.chunk_count,
                    "source_chars": len(section.body),
                    "corpus_run_id": checkpoint["corpus_run_id"],
                    "run_config_hash": checkpoint["run_config_hash"],
                },
                output_summary={
                    "obligations": len(payload.get("obligations", [])),
                    "needs_human_review": payload.get("needs_human_review", False),
                },
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_ms=duration_ms,
                model_name=str(checkpoint["model"]),
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
    section: SourceChunk, document_title: str
) -> tuple[dict[str, Any], int, int, int]:
    prompt = get_prompt("obligation_extractor")
    messages = prompt.format_messages(
        document_title=document_title,
        clause_number=(
            f"{section.section_number} chunk {section.chunk_index + 1}/{section.chunk_count}"
        ),
        clause_heading=section.section_title,
        text_content=section.body,
    )
    errors: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
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
                section=section.section_number,
                chunk=section.chunk_index,
                attempt=attempt,
                error=str(exc)[:500],
            )
            if attempt < MAX_ATTEMPTS:
                match = _RETRY_AFTER.search(str(exc))
                delay = float(match.group(1)) + 1.0 if match else min(60.0, 2.0**attempt)
                time.sleep(delay)
    raise RuntimeError(
        f"Section {section.section_number} chunk {section.chunk_index} failed across "
        f"{MAX_ATTEMPTS} Mistral attempts: " + " | ".join(errors)
    )


async def _extract_document(
    document: RegulatoryDocument, corpus_run_id: str, run_config: dict[str, Any]
) -> ExtractionRun:
    sections = _load_chunks(document.title)
    run = await _get_or_create_run(document, corpus_run_id, run_config)
    checkpoint = _checkpoint(run)
    completed = set(checkpoint["sections"])
    logger.info(
        "full_document_extraction_start",
        document=document.title,
        sections=len(sections),
        resumed=len(completed),
    )

    pending: list[SourceChunk] = []
    for section in sections:
        if section.checkpoint_key in completed:
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
        batch_started = time.monotonic()
        batch = pending[batch_start : batch_start + CONCURRENCY]
        for section in batch:
            logger.info(
                "full_section_extraction_start",
                document=document.title,
                section=section.section_number,
                chunk=f"{section.chunk_index + 1}/{section.chunk_count}",
                progress=f"{batch_start + batch.index(section) + 1}/{len(pending)}",
                chars=len(section.body),
            )

        async def extract_after_delay(section: SourceChunk, delay: float) -> Any:
            if delay > 0:
                await asyncio.sleep(delay)
            return await asyncio.to_thread(_extract_section, section, document.title)

        results = await asyncio.gather(
            *(
                extract_after_delay(section, index * REQUEST_START_INTERVAL_SECONDS)
                for index, section in enumerate(batch)
            ),
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
        # Preserve the observed rolling four-request window even when all calls return quickly.
        minimum_cycle = len(batch) * REQUEST_START_INTERVAL_SECONDS
        remaining = minimum_cycle - (time.monotonic() - batch_started)
        if remaining > 0 and batch_start + len(batch) < len(pending):
            await asyncio.sleep(remaining)

    async with async_session_maker() as db:
        refreshed = await db.get(ExtractionRun, run.id)
        if refreshed is None:
            raise RuntimeError(f"Extraction run disappeared: {run.id}")
        refreshed.current_stage = "ready_to_publish"
        await db.commit()
        return refreshed


def _as_json_list(value: Any) -> list[str] | None:
    null_markers = {"", "null", "none", "n/a", "not applicable", "not specified"}
    if value is None:
        return None
    if isinstance(value, list):
        normalized = [
            str(item).strip()
            for item in value
            if str(item).strip().casefold() not in null_markers
        ]
        return normalized or None
    text = str(value).strip()
    return [text] if text.casefold() not in null_markers else None


def _optional_text(value: Any, *, max_length: int | None = None) -> str | None:
    """Normalize model null sentinels and enforce typed registry string bounds."""
    if value is None:
        return None
    text = str(value).strip()
    if text.casefold() in {"", "null", "none", "n/a", "not applicable", "not specified"}:
        return None
    return text[:max_length] if max_length is not None else text


async def _publish_atomically(
    documents: Sequence[RegulatoryDocument],
    runs: list[ExtractionRun],
) -> dict[str, int]:
    provenance = assert_consistent_run_provenance(runs)
    sections_by_title = {title: _load_chunks(title) for title in DOCUMENT_TITLES}
    run_by_document = {run.document_id: run for run in runs}
    counts: dict[str, int] = {}

    async with async_session_maker() as db:
        document_ids = [document.id for document in documents]
        # Preserve all prior citations, validations, review tasks, controls, evidence mappings,
        # and audit events. Only active registry rows are superseded; historical rows remain
        # queryable through their original extraction-run provenance.
        previous_active = list(
            (
                await db.execute(
                    select(Obligation).where(
                        Obligation.document_id.in_(document_ids),
                        Obligation.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
        for obligation in previous_active:
            obligation.soft_delete()

        for document in documents:
            run = run_by_document[document.id]
            checkpoint = _checkpoint(run)
            if checkpoint["run_config_hash"] != provenance["run_config_hash"]:
                raise RuntimeError("Run configuration changed before publication")
            inserted = 0
            for order_index, section in enumerate(sections_by_title[document.title]):
                result = checkpoint["sections"].get(section.checkpoint_key)
                if result is None:
                    raise RuntimeError(
                        f"Missing completed section chunk {section.checkpoint_key} "
                        f"for {document.title}"
                    )
                payload = result["result"]
                obligations = payload.get("obligations", [])
                clause = Clause(
                    document_id=document.id,
                    clause_number=(
                        f"{section.section_number}.{section.chunk_index + 1}/{section.chunk_count}"
                    ),
                    clause_type=(
                        ClauseType.OBLIGATION if obligations else ClauseType.CONTEXTUAL_STATEMENT
                    ),
                    level=0,
                    order_index=2_000_000 + order_index,
                    text_content=section.body,
                    heading=(
                        f"{section.section_number}. {section.section_title} "
                        f"[chunk {section.chunk_index + 1}/{section.chunk_count}]"
                    ),
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
                    raw_frequency = _optional_text(candidate.get("frequency"))
                    obligation = Obligation(
                        organization_id=document.organization_id,
                        document_id=document.id,
                        clause_id=clause.id,
                        source_text=section.body,
                        normalized_obligation=candidate.get("normalized_obligation", ""),
                        actor=_optional_text(candidate.get("actor"), max_length=500) or "Unknown",
                        action=_optional_text(candidate.get("action")) or "Unknown",
                        object=_optional_text(candidate.get("object")),
                        conditions=_as_json_list(candidate.get("conditions")),
                        exceptions=_as_json_list(candidate.get("exceptions")),
                        frequency=_optional_text(raw_frequency, max_length=100),
                        deadline_description=_optional_text(
                            candidate.get("deadline_description")
                        ),
                        risk_level=risk_level,
                        risk_factors={
                            "model_self_confidence": candidate.get("self_confidence"),
                            "extraction_difficulty": candidate.get("difficulty"),
                            "untruncated_frequency": (
                                raw_frequency if raw_frequency and len(raw_frequency) > 100 else None
                            ),
                        },
                        extraction_method="agentic_full_section",
                        extraction_run_id=run.id,
                        prompt_version=PROMPT_VERSION,
                        model=provenance["model"],
                        citation_coordinates={
                            "section_number": section.section_number,
                            "chunk_index": section.chunk_index,
                            "chunk_count": section.chunk_count,
                            "chunk_char_start": section.char_start,
                            "chunk_char_end": section.char_end,
                            "provider": provenance["provider"],
                            "corpus_run_id": provenance["corpus_run_id"],
                            "run_config_hash": provenance["run_config_hash"],
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
                # Bound PostgreSQL/asyncpg statement parameter counts. The transaction remains
                # atomic, but SQLAlchemy cannot aggregate thousands of wide obligation rows into
                # one INSERT at commit time (asyncpg caps a statement at 32,767 parameters).
                await db.flush()

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
            document_db = await db.get(RegulatoryDocument, document.id)
            if document_db is None:
                raise RuntimeError(f"Document disappeared: {document.id}")
            document_db.status = DocumentStatus.PROCESSED
            document_db.processing_error = None
            counts[document.title] = inserted

        await db.commit()
    return counts


async def main() -> int:
    run_config = _run_config()
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

    corpus_run_id = await _resolve_corpus_run_id(documents, run_config)
    print(
        "FULL CORPUS RUN CONFIG: "
        f"provider={run_config['provider']} model={run_config['model']} "
        f"corpus_run_id={corpus_run_id} config={run_config['hash']}",
        flush=True,
    )
    runs: list[ExtractionRun] = []
    for document in documents:
        runs.append(await _extract_document(document, corpus_run_id, run_config))

    assert_consistent_run_provenance(runs)
    counts = await _publish_atomically(documents, runs)
    for title, count in counts.items():
        print(f"{title}: {count} obligations published pending verification", flush=True)
    print("FULL BOTH-SIDES EXTRACTION COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
