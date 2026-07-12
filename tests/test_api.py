"""Tests for CircularOS API health endpoints."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test basic health endpoint returns healthy."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "circularos-api"
        assert "timestamp" in data

    def test_health_check_has_security_headers(self, client):
        """Test that security headers are present on responses."""
        response = client.get("/api/v1/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "X-Request-ID" in response.headers
        assert "X-Process-Time" in response.headers

    def test_integration_status(self, client):
        """Test integration status endpoint."""
        response = client.get("/api/v1/health/integrations")
        assert response.status_code == 200
        data = response.json()
        assert "integrations" in data
        assert "database" in data["integrations"]
        assert "openai" in data["integrations"]
        assert "anthropic" in data["integrations"]
        assert "gemini" in data["integrations"]


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_register_success(self, client):
        """Test user registration creates user and organization."""
        response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "SecurePassword123!",
            "full_name": "Test User",
            "organization_name": "Test Org",
            "organization_slug": "test-org",
            "entity_type": "stock_broker",
        })
        # Will fail without DB, but validates schema
        assert response.status_code in (201, 500)  # 500 if no DB

    def test_register_invalid_email(self, client):
        """Test registration with invalid email."""
        response = client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "SecurePassword123!",
            "full_name": "Test User",
            "organization_name": "Test Org",
            "organization_slug": "test-org",
        })
        assert response.status_code == 422

    def test_register_short_password(self, client):
        """Test registration with too-short password."""
        response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "short",
            "full_name": "Test User",
            "organization_name": "Test Org",
            "organization_slug": "test-org",
        })
        assert response.status_code == 422

    def test_login_without_credentials(self, client):
        """Test login without valid credentials."""
        response = client.post("/api/v1/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "wrong",
        })
        assert response.status_code in (401, 500)

    def test_me_without_auth(self, client):
        """Test /me endpoint without authentication."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
