"""AI resilience and circuit breaker patterns.

Provides robust retry mechanisms and circuit breaking for LLM API calls
to handle rate limits, transient errors, and provider outages gracefully.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, TypeVar, cast
import structlog
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = structlog.get_logger()

T = TypeVar("T")

# Exceptions that should trigger a retry
class LLMRateLimitError(Exception):
    """Raised when an LLM provider rate limits us."""
    pass

class LLMTransientError(Exception):
    """Raised for 500, 502, 503, 504 errors from provider."""
    pass

class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open (failing fast)."""
    pass


class CircuitBreaker:
    """A simple async-safe circuit breaker."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"
        self._lock = asyncio.Lock()
        
    async def record_failure(self) -> None:
        async with self._lock:
            self.failures += 1
            self.last_failure_time = asyncio.get_event_loop().time()
            if self.failures >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning("circuit_breaker_opened", threshold=self.failure_threshold)

    async def record_success(self) -> None:
        async with self._lock:
            self.failures = 0
            self.state = "CLOSED"
            
    async def can_execute(self) -> bool:
        async with self._lock:
            if self.state == "CLOSED":
                return True
                
            # If OPEN, check if recovery timeout has passed
            current_time = asyncio.get_event_loop().time()
            if current_time - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("circuit_breaker_half_open")
                return True
                
            return False


# Global circuit breakers per provider
CIRCUIT_BREAKERS = {
    "openai": CircuitBreaker(),
    "anthropic": CircuitBreaker(),
    "google": CircuitBreaker()
}

def get_retry_policy(provider: str = "default") -> AsyncRetrying:
    """Get the standard tenacity retry policy for LLM calls."""
    import logging
    stdlib_logger = logging.getLogger("tenacity")
    
    return AsyncRetrying(
        # Wait exponentially from 1s to 30s, with jitter
        wait=wait_exponential_jitter(initial=1, max=30),
        # Stop after 6 attempts
        stop=stop_after_attempt(6),
        # Retry only on specific transient errors
        retry=(
            retry_if_exception_type(LLMRateLimitError) |
            retry_if_exception_type(LLMTransientError) |
            retry_if_exception_type(TimeoutError)
        ),
        before_sleep=before_sleep_log(stdlib_logger, logging.WARNING)
    )

async def execute_with_resilience(
    func: Callable[..., Any], 
    provider: str, 
    *args: Any, 
    **kwargs: Any
) -> Any:
    """Execute an LLM function wrapped in circuit breaker and retry logic."""
    breaker = CIRCUIT_BREAKERS.get(provider)
    
    if breaker and not await breaker.can_execute():
        raise CircuitOpenError(f"Circuit breaker for {provider} is OPEN. Failing fast.")
        
    try:
        # Apply tenacity retry logic
        async for attempt in get_retry_policy(provider):
            with attempt:
                result = await func(*args, **kwargs)
                
        # If we reach here, the call succeeded
        if breaker:
            await breaker.record_success()
        return result
        
    except Exception as e:
        # Record failure for circuit breaking
        if breaker and isinstance(e, (LLMRateLimitError, LLMTransientError, TimeoutError)):
            await breaker.record_failure()
        raise
