"""Base model mixins and utilities for all domain models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String, Boolean, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base


def generate_uuid7() -> uuid.UUID:
    """Generate a UUIDv7 (time-sortable).
    
    Falls back to UUIDv4 if uuid6 is not available.
    """
    try:
        from uuid6 import uuid7
        return uuid7()
    except ImportError:
        return uuid.uuid4()


class TimestampMixin:
    """Mixin adding created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin adding soft deletion support."""

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)


class VersionMixin:
    """Mixin adding optimistic locking via version counter."""

    version: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
    )


class AuditMixin:
    """Mixin adding audit fields for provenance tracking."""

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
