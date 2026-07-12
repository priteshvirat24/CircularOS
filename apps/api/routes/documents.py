"""Document management and ingestion routes."""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import get_settings
from apps.api.database import get_db
from apps.api.dependencies import get_current_user, get_org_id
from packages.regulatory_core.models.auth import User
from packages.regulatory_core.models.documents import (
    Clause, DocumentPage, DocumentSection, DocumentStatus, DocumentType,
    RegulatoryDocument,
)

router = APIRouter()


class IngestURLRequest(BaseModel):
    url: str
    title: str | None = None
    document_type: str | None = None
    reference_number: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[dict]
    total: int
    page: int
    page_size: int


@router.get("")
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    doc_type: str | None = Query(None, alias="type"),
    search: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List regulatory documents with filtering and pagination."""
    query = select(RegulatoryDocument).where(
        RegulatoryDocument.is_deleted == False
    )
    
    # Global documents (org_id is null) are visible to all
    # Org-specific documents require membership
    org_ids = [m.organization_id for m in user.memberships if m.is_active]
    query = query.where(
        (RegulatoryDocument.organization_id == None) |
        (RegulatoryDocument.organization_id.in_(org_ids))
    )
    
    if status_filter:
        try:
            query = query.where(RegulatoryDocument.status == DocumentStatus(status_filter))
        except ValueError:
            pass
    
    if doc_type:
        try:
            query = query.where(RegulatoryDocument.document_type == DocumentType(doc_type))
        except ValueError:
            pass
    
    if search:
        query = query.where(
            RegulatoryDocument.title.ilike(f"%{search}%") |
            RegulatoryDocument.reference_number.ilike(f"%{search}%")
        )
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # Paginate
    query = query.order_by(RegulatoryDocument.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    docs = result.scalars().all()
    
    return {
        "documents": [
            {
                "id": str(d.id),
                "title": d.title,
                "reference_number": d.reference_number,
                "document_type": d.document_type.value if d.document_type else None,
                "regulatory_domain": d.regulatory_domain.value if d.regulatory_domain else None,
                "status": d.status.value,
                "source_url": d.source_url,
                "issued_date": d.issued_date.isoformat() if d.issued_date else None,
                "page_count": d.page_count,
                "parsing_quality_score": d.parsing_quality_score,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get document details with metadata, clauses, and processing state."""
    doc = await db.get(RegulatoryDocument, document_id)
    if not doc or doc.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    # Get pages count
    pages_result = await db.execute(
        select(func.count()).where(DocumentPage.document_id == document_id)
    )
    pages_count = pages_result.scalar() or 0
    
    # Get clauses count
    clauses_result = await db.execute(
        select(func.count()).where(Clause.document_id == document_id)
    )
    clauses_count = clauses_result.scalar() or 0
    
    return {
        "id": str(doc.id),
        "title": doc.title,
        "reference_number": doc.reference_number,
        "document_type": doc.document_type.value if doc.document_type else None,
        "regulatory_domain": doc.regulatory_domain.value if doc.regulatory_domain else None,
        "status": doc.status.value,
        "source_url": doc.source_url,
        "download_url": doc.download_url,
        "file_path": doc.file_path,
        "file_size_bytes": doc.file_size_bytes,
        "mime_type": doc.mime_type,
        "sha256_hash": doc.sha256_hash,
        "page_count": doc.page_count,
        "issued_date": doc.issued_date.isoformat() if doc.issued_date else None,
        "effective_date": doc.effective_date.isoformat() if doc.effective_date else None,
        "issuing_authority": doc.issuing_authority,
        "subject": doc.subject,
        "applicable_to": doc.applicable_to,
        "keywords": doc.keywords,
        "parsing_quality_score": doc.parsing_quality_score,
        "ocr_applied": doc.ocr_applied,
        "processing_error": doc.processing_error,
        "pages_extracted": pages_count,
        "clauses_extracted": clauses_count,
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat(),
    }


@router.get("/{document_id}/clauses")
async def get_document_clauses(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all clauses for a document."""
    doc = await db.get(RegulatoryDocument, document_id)
    if not doc or doc.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    result = await db.execute(
        select(Clause)
        .where(Clause.document_id == document_id)
        .order_by(Clause.order_index)
    )
    clauses = result.scalars().all()
    
    return {
        "document_id": str(document_id),
        "clauses": [
            {
                "id": str(c.id),
                "clause_number": c.clause_number,
                "clause_type": c.clause_type.value if c.clause_type else None,
                "level": c.level,
                "heading": c.heading,
                "text_content": c.text_content,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "classification_confidence": c.classification_confidence,
                "parent_clause_id": str(c.parent_clause_id) if c.parent_clause_id else None,
            }
            for c in clauses
        ],
        "total": len(clauses),
    }


@router.get("/{document_id}/pages")
async def get_document_pages(
    document_id: uuid.UUID,
    page: int = Query(1, ge=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get document page content."""
    result = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    )
    pages = result.scalars().all()
    
    return {
        "document_id": str(document_id),
        "pages": [
            {
                "id": str(p.id),
                "page_number": p.page_number,
                "text_content": p.text_content,
                "has_tables": p.has_tables,
                "word_count": p.word_count,
            }
            for p in pages
        ],
    }


@router.post("/ingest/url", status_code=status.HTTP_202_ACCEPTED)
async def ingest_from_url(
    body: IngestURLRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest a regulatory document from a URL."""
    # Check for duplicate URL
    existing = await db.execute(
        select(RegulatoryDocument).where(
            RegulatoryDocument.source_url == body.url,
            RegulatoryDocument.is_deleted == False,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document with this URL already exists",
        )
    
    # Create document record
    doc = RegulatoryDocument(
        title=body.title or "Untitled Document",
        source_url=body.url,
        download_url=body.url,
        reference_number=body.reference_number,
        document_type=DocumentType(body.document_type) if body.document_type else DocumentType.CIRCULAR,
        status=DocumentStatus.PENDING,
        created_by=user.id,
    )
    db.add(doc)
    await db.flush()
    
    # Dispatch Celery task for download and processing
    from apps.worker.tasks.document import process_document_task
    process_document_task.delay(str(doc.id))
    
    return {
        "document_id": str(doc.id),
        "status": "pending",
        "message": "Document queued for ingestion. Processing will begin shortly.",
    }


@router.post("/ingest/upload", status_code=status.HTTP_202_ACCEPTED)
async def ingest_from_upload(
    file: UploadFile = File(...),
    title: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload and ingest a regulatory PDF document."""
    settings = get_settings()
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid MIME type. Expected application/pdf")
    
    # Read and hash file
    content = await file.read()
    
    # Check file size
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB",
        )
    
    sha256 = hashlib.sha256(content).hexdigest()
    
    # Check for duplicate
    existing = await db.execute(
        select(RegulatoryDocument).where(
            RegulatoryDocument.sha256_hash == sha256,
            RegulatoryDocument.is_deleted == False,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document with this content already exists (duplicate SHA-256)",
        )
    
    # Save file
    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{sha256}.pdf")
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Create document record
    doc = RegulatoryDocument(
        title=title or file.filename,
        file_path=file_path,
        file_size_bytes=len(content),
        mime_type="application/pdf",
        sha256_hash=sha256,
        status=DocumentStatus.DOWNLOADED,
        created_by=user.id,
    )
    db.add(doc)
    await db.flush()
    
    # Dispatch processing task
    from apps.worker.tasks.document import process_document_task
    process_document_task.delay(str(doc.id))
    
    return {
        "document_id": str(doc.id),
        "sha256": sha256,
        "status": "downloaded",
        "message": "Document uploaded successfully. Processing will begin shortly.",
    }
