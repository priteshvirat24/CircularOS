"""Document acquisition: download from URL, verify integrity, detect duplicates."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog

from apps.api.config import get_settings

logger = structlog.get_logger()


@dataclass
class AcquisitionResult:
    """Result of a document acquisition attempt."""
    success: bool
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    sha256_hash: Optional[str] = None
    mime_type: Optional[str] = None
    source_url: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    source_headers: Optional[dict] = None
    error: Optional[str] = None


async def download_document(url: str, timeout: float = 60.0) -> AcquisitionResult:
    """Download a regulatory document from a URL.
    
    Stores the file locally with SHA-256 hash as filename.
    Validates MIME type and file size.
    """
    settings = get_settings()
    
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "CircularOS/0.1 (Regulatory Document Processor)",
            },
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            content = response.content
            content_type = response.headers.get("content-type", "")
            
            # Validate MIME type
            if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
                logger.warning(
                    "unexpected_mime_type",
                    url=url,
                    content_type=content_type,
                )
            
            # Check file size
            max_size = settings.max_upload_size_mb * 1024 * 1024
            if len(content) > max_size:
                return AcquisitionResult(
                    success=False,
                    error=f"File too large: {len(content)} bytes (max: {max_size})",
                )
            
            # Calculate hash
            sha256 = hashlib.sha256(content).hexdigest()
            
            # Save file
            upload_dir = settings.upload_dir
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, f"{sha256}.pdf")
            
            with open(file_path, "wb") as f:
                f.write(content)
            
            logger.info(
                "document_downloaded",
                url=url,
                sha256=sha256,
                size=len(content),
            )
            
            return AcquisitionResult(
                success=True,
                file_path=file_path,
                file_size_bytes=len(content),
                sha256_hash=sha256,
                mime_type=content_type.split(";")[0].strip() if content_type else "application/pdf",
                source_url=url,
                retrieved_at=datetime.now(timezone.utc),
                source_headers=dict(response.headers),
            )
    
    except httpx.HTTPStatusError as e:
        logger.error("download_http_error", url=url, status=e.response.status_code)
        return AcquisitionResult(success=False, error=f"HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error("download_request_error", url=url, error=str(e))
        return AcquisitionResult(success=False, error=str(e))
    except Exception as e:
        logger.error("download_unexpected_error", url=url, error=str(e))
        return AcquisitionResult(success=False, error=str(e))


def verify_integrity(
    file_path: str,
    expected_hash: Optional[str] = None,
) -> dict:
    """Verify document integrity: file exists, valid PDF, hash match."""
    result = {
        "valid": True,
        "checks": {},
    }
    
    # File existence
    if not os.path.exists(file_path):
        return {"valid": False, "checks": {"exists": False}, "error": "File not found"}
    result["checks"]["exists"] = True
    
    # File size
    size = os.path.getsize(file_path)
    result["checks"]["size_bytes"] = size
    if size == 0:
        result["valid"] = False
        result["error"] = "File is empty"
        return result
    
    # Read file
    with open(file_path, "rb") as f:
        content = f.read()
    
    # PDF magic bytes check
    is_pdf = content[:5] == b"%PDF-"
    result["checks"]["is_pdf"] = is_pdf
    if not is_pdf:
        result["valid"] = False
        result["error"] = "File is not a valid PDF (missing %PDF- header)"
        return result
    
    # SHA-256
    sha256 = hashlib.sha256(content).hexdigest()
    result["checks"]["sha256"] = sha256
    
    if expected_hash and sha256 != expected_hash:
        result["valid"] = False
        result["error"] = f"Hash mismatch: expected {expected_hash}, got {sha256}"
        return result
    
    result["checks"]["hash_verified"] = expected_hash is not None
    
    return result
