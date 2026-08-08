"""Pytest configuration and fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _null_pool_engine():
    """Bind the whole suite to the dedicated TEST database with a NullPool engine.

    Two things happen here, in order:

    1. The app's global engine/session factory are rebound to ``test_database_url`` (NullPool,
       because Starlette's TestClient runs each request in a fresh event loop and a pooled
       asyncpg connection cached on a closed loop raises "Event loop is closed"). The dev DB is
       never opened.
    2. Before truncating anything, ``require_test_database`` checks the *live* connection's
       ``current_database()`` — so even if the URL were misconfigured, a non-test database
       aborts the run instead of being wiped. This is the hard guard that makes the Phase-2
       dev-data-loss footgun structurally impossible.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    import apps.api.database as db
    from apps.api.config import get_settings

    test_url = get_settings().test_database_url
    db._engine = create_async_engine(test_url, poolclass=NullPool)
    db._session_factory = async_sessionmaker(
        bind=db._engine, class_=AsyncSession, expire_on_commit=False
    )

    # The auth tests create fixed users/orgs and commit them. Start from a clean auth slate so
    # the suite is repeatable — but only ever against a verified test database.
    import asyncio

    from sqlalchemy import text

    from tests.dbsafety import require_test_database

    async def _clean_auth_tables() -> None:
        async with db._engine.begin() as conn:
            live_db = (await conn.execute(text("SELECT current_database()"))).scalar()
            require_test_database(live_db)  # hard-abort if this is not a test database
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
