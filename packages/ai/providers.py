"""LLM Provider abstraction and routing.

Supports OpenAI, Anthropic, Gemini (with multi-key rotation), Mistral, and Groq
(the latter two via OpenAI-compatible endpoints). The routing layer maps three logical
slots — fast, reasoning, critic — to concrete provider/model pairs set in .env.
"""

from __future__ import annotations

import itertools
import threading
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from pydantic import BaseModel, SecretStr

from apps.api.config import get_settings

logger = structlog.get_logger()

# ── Gemini key rotation ───────────────────────────────────────────────
# Rate limits are per-project, so keys from different Google Cloud projects
# genuinely multiply quota. We cycle through all configured keys round-robin.
# Thread-safe via a lock (the cycle iterator itself is not).

_gemini_pool_lock = threading.Lock()
_gemini_pool: itertools.cycle[str] | None = None
_gemini_pool_size: int = 0


def _init_gemini_pool() -> None:
    """Build the key pool once from settings. Called lazily on first use."""
    global _gemini_pool, _gemini_pool_size
    settings = get_settings()
    keys: list[str] = []

    # Primary key
    if settings.gemini_api_key:
        keys.append(settings.gemini_api_key)

    # Additional keys: GEMINI_API_KEY_2 … GEMINI_API_KEY_10
    for i in range(2, 11):
        k = getattr(settings, f"gemini_api_key_{i}", None)
        if k:
            keys.append(k)

    if not keys:
        raise ValueError(
            "No Gemini API key configured. Set GEMINI_API_KEY (and optionally "
            "GEMINI_API_KEY_2 … GEMINI_API_KEY_10 from different GCP projects "
            "to multiply your free-tier quota)."
        )

    _gemini_pool = itertools.cycle(keys)
    _gemini_pool_size = len(keys)
    logger.info("gemini_key_pool_initialized", pool_size=_gemini_pool_size)


def _next_gemini_key() -> str:
    """Return the next Gemini key from the rotation pool."""
    global _gemini_pool
    with _gemini_pool_lock:
        if _gemini_pool is None:
            _init_gemini_pool()
        assert _gemini_pool is not None
        return next(_gemini_pool)


# ── Provider constructors ─────────────────────────────────────────────


def get_openai_model(model_name: str, temperature: float = 0.0, **kwargs: Any) -> BaseChatModel:
    """Initialize OpenAI chat model."""
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        api_key=SecretStr(settings.openai_api_key),
        base_url=settings.openai_base_url,
        max_retries=3,
        **kwargs,
    )


def get_anthropic_model(model_name: str, temperature: float = 0.0, **kwargs: Any) -> BaseChatModel:
    """Initialize Anthropic chat model."""
    from langchain_anthropic import ChatAnthropic

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured")

    return ChatAnthropic(
        model_name=model_name,
        temperature=temperature,
        api_key=SecretStr(settings.anthropic_api_key),
        max_retries=3,
        **kwargs,
    )


def get_gemini_model(model_name: str, temperature: float = 0.0, **kwargs: Any) -> BaseChatModel:
    """Initialize Google Gemini chat model with automatic key rotation.

    Keys rotate round-robin across all configured GEMINI_API_KEY[_N] values.
    Each key should come from a different GCP project to multiply free-tier RPD.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = _next_gemini_key()

    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=api_key,
        max_retries=3,
        **kwargs,
    )


def get_groq_model(model_name: str, temperature: float = 0.0, **kwargs: Any) -> BaseChatModel:
    """Initialize Groq chat model via the OpenAI-compatible endpoint.

    Groq runs open-source models (Llama, GPT-OSS, Qwen) on LPU hardware at
    300-1000 tok/s. Free tier: 30 RPM, 1K RPD per model, no credit card.
    Uses ChatOpenAI with a base-URL swap — no extra dependency needed.
    """
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not configured. Get one free at console.groq.com")

    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        api_key=SecretStr(settings.groq_api_key),
        base_url="https://api.groq.com/openai/v1",
        max_retries=3,
        **kwargs,
    )


def get_mistral_model(model_name: str, temperature: float = 0.0, **kwargs: Any) -> BaseChatModel:
    """Initialize Mistral La Plateforme through its OpenAI-compatible endpoint."""
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    if not settings.mistral_api_key:
        raise ValueError(
            "MISTRAL_API_KEY is not configured. Set it before routing a model to Mistral."
        )

    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        api_key=SecretStr(settings.mistral_api_key),
        base_url="https://api.mistral.ai/v1",
        max_retries=3,
        **kwargs,
    )


# ── Routing ───────────────────────────────────────────────────────────

# Default fallbacks per slot (used when .env doesn't specify).
# Gemini Flash for reasoning (best structured output on free tier),
# Groq for fast/critic (high RPD + different model family for the critic).
_SLOT_DEFAULTS: dict[str, tuple[str, str]] = {
    "fast": ("groq", "openai/gpt-oss-120b"),
    "reasoning": ("gemini", "gemini-2.5-flash"),
    "critic": ("groq", "openai/gpt-oss-120b"),
}

_PROVIDER_FACTORIES = {
    "openai": get_openai_model,
    "anthropic": get_anthropic_model,
    "gemini": get_gemini_model,
    "groq": get_groq_model,
    "mistral": get_mistral_model,
}


def get_llm(
    routing_type: str = "reasoning",
    temperature: float = 0.0,
    **kwargs: Any,
) -> BaseChatModel:
    """Get the appropriate LLM based on routing configuration.

    Args:
        routing_type: "fast", "reasoning", or "critic"
        temperature: Model temperature (default 0.0 for deterministic extraction)
    """
    settings = get_settings()
    default_provider, default_model = _SLOT_DEFAULTS.get(
        routing_type, ("gemini", "gemini-2.5-flash")
    )

    if routing_type == "fast":
        provider = settings.fast_model_provider or default_provider
        model_name = settings.fast_model_name or default_model
    elif routing_type == "critic":
        provider = settings.critic_model_provider or default_provider
        model_name = settings.critic_model_name or default_model
    else:  # reasoning
        provider = settings.reasoning_model_provider or default_provider
        model_name = settings.reasoning_model_name or default_model

    logger.debug(
        "llm_routing",
        routing_type=routing_type,
        provider=provider,
        model=model_name,
    )

    factory = _PROVIDER_FACTORIES.get(provider)
    if factory is None:
        raise ValueError(
            f"Unknown LLM provider: {provider!r}. Available: {', '.join(_PROVIDER_FACTORIES)}"
        )

    return factory(model_name, temperature, **kwargs)


def get_structured_llm(
    schema: type[BaseModel],
    routing_type: str = "reasoning",
    temperature: float = 0.0,
    **kwargs: Any,
) -> Runnable[Any, Any]:
    """Get an LLM bound to output a specific Pydantic schema."""
    llm = get_llm(routing_type, temperature, **kwargs)
    settings = get_settings()
    if (
        routing_type == "critic"
        and settings.critic_model_provider == "groq"
        and (settings.critic_model_name or "").startswith("llama-")
    ):
        # Groq's high-capacity free Llama model supports JSON Object mode but not
        # strict json_schema response_format. LangChain still parses it into ``schema``.
        return llm.with_structured_output(schema, method="json_mode")
    return llm.with_structured_output(schema)
