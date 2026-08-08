"""Celery task wrapper for the regulatory diff.

All logic lives in ``apps.api.services.diff_service`` (no Celery dependency) so the API can call
it inline; this module only adds the queue/retry wrapper for background execution.
"""

from __future__ import annotations

import asyncio

import structlog
from celery import Task  # type: ignore[import-untyped]

from apps.api.services.diff_service import run_diff_async
from apps.worker.main import app

logger = structlog.get_logger()

# Re-exported so existing imports of the async entrypoint keep working.
__all__ = ["run_diff_async", "run_diff_task"]


@app.task(bind=True, max_retries=2)
def run_diff_task(self: Task, old_document_id: str, new_document_id: str,
                  created_by: str | None = None) -> str:
    """Execute the regulatory diff on two documents as a background job."""
    try:
        return asyncio.run(run_diff_async(old_document_id, new_document_id, created_by))
    except Exception as exc:  # noqa: BLE001
        logger.error("diff_task_failed_retrying", error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries) from exc
