"""Celery tasks for document acquisition and parsing."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from celery import shared_task
from sqlalchemy import select

from apps.api.database import async_session_maker
from apps.worker.main import app
from packages.document_processing.acquisition import download_document, verify_integrity
from packages.document_processing.parser import parse_pdf, reconstruct_clause_hierarchy
from packages.regulatory_core.models.documents import (
    Clause, DocumentPage, DocumentStatus, RegulatoryDocument,
)

logger = structlog.get_logger()


async def process_document_async(document_id: str) -> None:
    """Async implementation of document processing."""
    async with async_session_maker() as db:
        doc = await db.get(RegulatoryDocument, uuid.UUID(document_id))
        if not doc:
            logger.error("document_not_found", document_id=document_id)
            return

        doc.status = DocumentStatus.PROCESSING
        await db.commit()

        try:
            # 1. Acquisition
            if not doc.file_path and doc.source_url:
                logger.info("downloading_document", url=doc.source_url)
                result = await download_document(doc.source_url)
                
                if not result.success:
                    raise ValueError(f"Download failed: {result.error}")
                    
                doc.file_path = result.file_path
                doc.file_size_bytes = result.file_size_bytes
                doc.sha256_hash = result.sha256_hash
                doc.mime_type = result.mime_type
                
            # 2. Verify Integrity
            if not doc.file_path:
                raise ValueError("No file path available for processing")
                
            integrity = verify_integrity(doc.file_path, expected_hash=doc.sha256_hash)
            if not integrity["valid"]:
                raise ValueError(f"Integrity check failed: {integrity.get('error')}")

            # 3. Parsing
            logger.info("parsing_document", file=doc.file_path)
            parsed_doc = parse_pdf(doc.file_path)
            
            doc.page_count = parsed_doc.page_count
            doc.parsing_quality_score = parsed_doc.quality_score
            doc.ocr_applied = parsed_doc.needs_ocr
            
            # Save pages
            for page in parsed_doc.pages:
                doc_page = DocumentPage(
                    document_id=doc.id,
                    page_number=page.page_number,
                    text_content=page.text_content,
                    has_tables=page.has_tables,
                    has_images=page.has_images,
                    word_count=page.word_count,
                    tables_json=page.tables if page.tables else None,
                )
                db.add(doc_page)
            
            # Reconstruct and save clauses
            clauses = reconstruct_clause_hierarchy(parsed_doc.headings, parsed_doc.pages)
            for clause_dict in clauses:
                clause = Clause(
                    document_id=doc.id,
                    clause_number=clause_dict["clause_number"],
                    heading=clause_dict["heading"],
                    text_content=clause_dict["text_content"],
                    level=clause_dict["level"],
                    page_start=clause_dict["page_start"],
                    page_end=clause_dict["page_end"],
                    order_index=clause_dict["order_index"],
                )
                db.add(clause)
            
            doc.status = DocumentStatus.EXTRACTING
            await db.commit()
            
            # 4. Trigger LangGraph extraction
            from apps.worker.tasks.extraction import run_extraction_workflow_task
            run_extraction_workflow_task.delay(str(doc.id))

        except Exception as e:
            logger.exception("document_processing_failed", document_id=document_id)
            doc.status = DocumentStatus.FAILED
            doc.processing_error = str(e)
            await db.commit()


@app.task(bind=True, max_retries=3)
def process_document_task(self, document_id: str) -> None:
    """Celery task to download, verify, and parse a document."""
    try:
        # Run async function in sync context
        asyncio.run(process_document_async(document_id))
    except Exception as exc:
        logger.error("task_failed_retrying", task="process_document", error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
