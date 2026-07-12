"""Pytest configuration and fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app():
    """Create FastAPI application for testing."""
    from apps.api.main import app
    return app


@pytest.fixture(scope="session")
def client(app):
    """Create test client."""
    return TestClient(app)
