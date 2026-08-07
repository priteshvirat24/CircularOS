"""Pytest configuration and fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _null_pool_engine():
    """Use a NullPool async engine for tests.

    Starlette's TestClient runs each request in a fresh event loop. The
    application's default pooled asyncpg engine caches connections bound to
    the loop that first opened them, so a later request reuses a connection
    whose loop is already closed ("Event loop is closed"). NullPool opens and
    closes a connection per request, keeping every connection on its own loop.
    Production engine configuration is unaffected.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    import apps.api.database as db
    from apps.api.config import get_settings

    db._engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    db._session_factory = async_sessionmaker(
        bind=db._engine, class_=AsyncSession, expire_on_commit=False
    )

    # The auth tests create fixed users/orgs and commit them. Start from a
    # clean auth slate so the suite is repeatable against a persistent dev DB.
    import asyncio

    from sqlalchemy import text

    async def _clean_auth_tables() -> None:
        async with db._engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE audit_events, refresh_tokens, "
                    "organization_memberships, users, organizations "
                    "RESTART IDENTITY CASCADE"
                )
            )

    asyncio.run(_clean_auth_tables())
    yield


@pytest.fixture(scope="session")
def app():
    """Create FastAPI application for testing."""
    from apps.api.main import app
    return app


@pytest.fixture(scope="session")
def client(app):
    """Create test client."""
    return TestClient(app)
