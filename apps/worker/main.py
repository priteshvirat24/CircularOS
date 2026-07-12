"""Celery worker application for CircularOS background processing."""

from __future__ import annotations

import os
import sys

from celery import Celery
from celery.signals import worker_init

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from apps.api.config import get_settings

settings = get_settings()

app = Celery(
    "circularos",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # For reliability: ack after completion
    worker_prefetch_multiplier=1,  # One task at a time per worker
    task_reject_on_worker_lost=True,
    task_default_queue="circularos",
    task_routes={
        "apps.worker.tasks.document.*": {"queue": "documents"},
        "apps.worker.tasks.extraction.*": {"queue": "extraction"},
        "apps.worker.tasks.evaluation.*": {"queue": "evaluation"},
    },
    # Result expiry
    result_expires=86400,  # 24 hours
)

# Auto-discover tasks
app.autodiscover_tasks(["apps.worker.tasks"])


@worker_init.connect
def on_worker_init(**kwargs):
    """Initialize worker dependencies on startup."""
    import structlog
    logger = structlog.get_logger()
    logger.info("circularos_worker_starting", environment=settings.app_env.value)
    
    integrations = settings.get_integration_status()
    for name, status in integrations.items():
        level = "info" if status["configured"] else "warning"
        getattr(logger, level)(
            "worker_integration_status",
            integration=name,
            status=status["status"],
        )
