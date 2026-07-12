"""LLM Provider abstraction and routing."""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel
import structlog

from apps.api.config import get_settings

logger = structlog.get_logger()


def get_openai_model(model_name: str, temperature: float = 0.0, **kwargs) -> BaseChatModel:
    """Initialize OpenAI chat model."""
    from langchain_openai import ChatOpenAI
    settings = get_settings()
    
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured")
        
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        max_retries=3,
        **kwargs
    )


def get_anthropic_model(model_name: str, temperature: float = 0.0, **kwargs) -> BaseChatModel:
    """Initialize Anthropic chat model."""
    from langchain_anthropic import ChatAnthropic
    settings = get_settings()
    
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured")
        
    return ChatAnthropic(
        model_name=model_name,
        temperature=temperature,
        api_key=settings.anthropic_api_key,
        max_retries=3,
        **kwargs
    )


def get_gemini_model(model_name: str, temperature: float = 0.0, **kwargs) -> BaseChatModel:
    """Initialize Google Gemini chat model."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    settings = get_settings()
    
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not configured")
        
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=settings.gemini_api_key,
        max_retries=3,
        **kwargs
    )


def get_llm(
    routing_type: str = "reasoning", 
    temperature: float = 0.0,
    **kwargs
) -> BaseChatModel:
    """Get the appropriate LLM based on routing configuration.
    
    Args:
        routing_type: "fast", "reasoning", or "critic"
        temperature: Model temperature
    """
    settings = get_settings()
    
    if routing_type == "fast":
        provider = settings.fast_model_provider or "openai"
        model_name = settings.fast_model_name or "gpt-4o-mini"
    elif routing_type == "critic":
        provider = settings.critic_model_provider or "anthropic"
        model_name = settings.critic_model_name or "claude-3-5-sonnet-20240620"
    else:  # reasoning
        provider = settings.reasoning_model_provider or "openai"
        model_name = settings.reasoning_model_name or "gpt-4o"
        
    logger.debug("llm_routing", routing_type=routing_type, provider=provider, model=model_name)
    
    if provider == "openai":
        return get_openai_model(model_name, temperature, **kwargs)
    elif provider == "anthropic":
        return get_anthropic_model(model_name, temperature, **kwargs)
    elif provider == "gemini":
        return get_gemini_model(model_name, temperature, **kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def get_structured_llm(
    schema: Type[BaseModel],
    routing_type: str = "reasoning",
    temperature: float = 0.0,
    **kwargs
) -> BaseChatModel:
    """Get an LLM bound to output a specific Pydantic schema."""
    llm = get_llm(routing_type, temperature, **kwargs)
    return llm.with_structured_output(schema)
