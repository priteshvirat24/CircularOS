"""CircularOS API Configuration.

All configuration is loaded from environment variables.
Validates required settings on startup and reports unconfigured integrations.
"""

from __future__ import annotations

import secrets
from enum import Enum
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class EmbeddingProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────
    app_name: str = "CircularOS"
    app_env: Environment = Environment.DEVELOPMENT
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # ── Database ─────────────────────────────────
    database_url: str = "postgresql+asyncpg://circularos:circularos_dev@localhost:5432/circularos"
    database_sync_url: str = "postgresql://circularos:circularos_dev@localhost:5432/circularos"

    # ── Redis ────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Authentication ───────────────────────────
    jwt_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    encryption_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    # ── CORS ─────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ── LLM Providers ────────────────────────────
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-20250514"

    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"

    # ── Model Routing ────────────────────────────
    fast_model_provider: Optional[str] = None
    fast_model_name: Optional[str] = None

    reasoning_model_provider: Optional[str] = None
    reasoning_model_name: Optional[str] = None

    critic_model_provider: Optional[str] = None
    critic_model_name: Optional[str] = None

    # ── Embedding ────────────────────────────────
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dimensions: int = 1536

    # ── Reranker ─────────────────────────────────
    reranker_provider: Optional[str] = None
    reranker_model: Optional[str] = None

    # ── Observability ────────────────────────────
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"

    otel_exporter_otlp_endpoint: Optional[str] = None
    otel_service_name: str = "circularos"

    log_level: str = "INFO"
    log_format: str = "json"

    # ── Knowledge Graph ──────────────────────────
    neo4j_uri: Optional[str] = None
    neo4j_username: Optional[str] = None
    neo4j_password: Optional[str] = None

    # ── External Sources ─────────────────────────
    sebi_source_base_url: str = "https://www.sebi.gov.in"

    # ── File Storage ─────────────────────────────
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 50

    # ── Rate Limiting ────────────────────────────
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10

    # ── Worker ───────────────────────────────────
    worker_concurrency: int = 4

    def get_integration_status(self) -> dict[str, dict[str, bool | str]]:
        """Report which integrations are configured vs unconfigured."""
        return {
            "database": {
                "configured": bool(self.database_url),
                "status": "configured" if self.database_url else "unconfigured",
            },
            "redis": {
                "configured": bool(self.redis_url),
                "status": "configured" if self.redis_url else "unconfigured",
            },
            "openai": {
                "configured": bool(self.openai_api_key),
                "status": "configured" if self.openai_api_key else "unconfigured - set OPENAI_API_KEY",
            },
            "anthropic": {
                "configured": bool(self.anthropic_api_key),
                "status": "configured" if self.anthropic_api_key else "unconfigured - set ANTHROPIC_API_KEY",
            },
            "gemini": {
                "configured": bool(self.gemini_api_key),
                "status": "configured" if self.gemini_api_key else "unconfigured - set GEMINI_API_KEY",
            },
            "embedding": {
                "configured": bool(self.embedding_provider and self.embedding_model),
                "status": (
                    f"configured ({self.embedding_provider}/{self.embedding_model})"
                    if self.embedding_provider and self.embedding_model
                    else "unconfigured - set EMBEDDING_PROVIDER and EMBEDDING_MODEL"
                ),
            },
            "langfuse": {
                "configured": bool(self.langfuse_public_key and self.langfuse_secret_key),
                "status": (
                    "configured"
                    if self.langfuse_public_key and self.langfuse_secret_key
                    else "unconfigured - set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY"
                ),
            },
            "neo4j": {
                "configured": bool(self.neo4j_uri and self.neo4j_username),
                "status": (
                    "configured"
                    if self.neo4j_uri
                    else "unconfigured - using PostgreSQL graph tables"
                ),
            },
        }

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if v == "CHANGE_ME_TO_A_RANDOM_64_CHAR_SECRET":
            import warnings
            warnings.warn(
                "JWT_SECRET is using default value. Set a secure random value in production.",
                UserWarning,
                stacklevel=2,
            )
        return v


# Singleton settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
