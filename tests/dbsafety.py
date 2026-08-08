"""Safety guard: refuse destructive test cleanup against anything but a test database.

The pytest suite truncates tables between/around runs. If it is ever pointed at the dev (or
prod) database, ``TRUNCATE ... CASCADE`` silently destroys real corpus data (this happened
during Phase 2). ``require_test_database`` makes that structurally impossible: the truncating
fixture calls it with the live database name and it raises unless the name marks a test DB.
"""

from __future__ import annotations

import re


class UnsafeDatabaseError(RuntimeError):
    """Raised when a destructive test operation is attempted on a non-test database."""


def is_test_database_name(db_name: str | None) -> bool:
    """True only for a database whose name marks it as a throwaway test DB (contains 'test')."""
    if not db_name:
        return False
    return "test" in db_name.strip().casefold()


def database_name_from_url(url: str | None) -> str | None:
    """Extract the database name from a SQLAlchemy/libpq URL (the path after the last '/')."""
    if not url:
        return None
    tail = url.rsplit("/", 1)[-1]
    return re.split(r"[?#]", tail)[0] or None


def require_test_database(db_name: str | None) -> None:
    """Raise ``UnsafeDatabaseError`` unless ``db_name`` is a test database.

    This is the hard gate that must run before any TRUNCATE in the test suite.
    """
    if not is_test_database_name(db_name):
        raise UnsafeDatabaseError(
            f"Refusing destructive test cleanup on non-test database {db_name!r}. "
            f"Point the test suite at a database whose name contains 'test' "
            f"(set TEST_DATABASE_URL / TEST_DATABASE_SYNC_URL)."
        )
