"""Tests for the destructive-cleanup safety guard and test-DB isolation."""

from __future__ import annotations

import pytest

from tests.dbsafety import (
    UnsafeDatabaseError,
    database_name_from_url,
    is_test_database_name,
    require_test_database,
)


@pytest.mark.parametrize("name", ["circularos_test", "test", "myapp_test", "TEST_DB"])
def test_require_test_database_allows_test_names(name):
    require_test_database(name)  # must not raise


@pytest.mark.parametrize("name", ["circularos", "prod", "circularos_dev", "", None])
def test_require_test_database_aborts_non_test(name):
    with pytest.raises(UnsafeDatabaseError):
        require_test_database(name)


def test_is_test_database_name():
    assert is_test_database_name("circularos_test")
    assert not is_test_database_name("circularos")
    assert not is_test_database_name(None)


def test_database_name_from_url():
    assert database_name_from_url(
        "postgresql+asyncpg://u:p@localhost:5433/circularos_test"
    ) == "circularos_test"
    assert database_name_from_url(
        "postgresql://u:p@h:5433/circularos_test?sslmode=require"
    ) == "circularos_test"
    assert database_name_from_url(None) is None


@pytest.mark.asyncio
async def test_suite_is_bound_to_a_test_database():
    """Proof of isolation: the live app engine the suite uses points at a *test* database."""
    from sqlalchemy import text

    from apps.api.database import get_engine

    async with get_engine().connect() as conn:
        live_db = (await conn.execute(text("SELECT current_database()"))).scalar()
    assert is_test_database_name(live_db), f"suite is bound to non-test DB {live_db!r}"
