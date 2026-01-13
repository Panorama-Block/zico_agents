"""
Retry utilities with exponential backoff.

Provides retry logic for unreliable operations like LLM calls.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, TypeVar, ParamSpec

logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 30.0  # Maximum delay in seconds
    exponential_base: float = 2.0  # Exponential backoff base
    retryable_exceptions: tuple = field(
        default_factory=lambda: (TimeoutError, ConnectionError, Exception)
    )


# Default configuration
DEFAULT_RETRY_CONFIG = RetryConfig()


async def execute_with_retry(
    func: Callable[P, T],
    *args: P.args,
    config: RetryConfig | None = None,
    fallback_response: T | None = None,
    on_retry: Callable[[int, Exception], None] | None = None,
    **kwargs: P.kwargs,
) -> T:
    """
    Execute a function with retry logic and exponential backoff.

    Args:
        func: Function to execute (can be sync or async)
        *args: Positional arguments for the function
        config: Retry configuration (uses defaults if None)
        fallback_response: Value to return if all retries fail (if None, raises exception)
        on_retry: Optional callback called on each retry (receives attempt number and exception)
        **kwargs: Keyword arguments for the function

    Returns:
        The function result or fallback_response

    Raises:
        The last exception if all retries fail and no fallback is provided
    """
    config = config or DEFAULT_RETRY_CONFIG
    last_exception: Exception | None = None

    for attempt in range(config.max_retries):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        except config.retryable_exceptions as e:
            last_exception = e
            is_last_attempt = attempt >= config.max_retries - 1

            if is_last_attempt:
                logger.error(
                    f"All {config.max_retries} attempts failed for {func.__name__}. "
                    f"Last error: {e}"
                )
            else:
                # Calculate delay with exponential backoff
                delay = min(
                    config.base_delay * (config.exponential_base**attempt),
                    config.max_delay,
                )

                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_retries} failed for {func.__name__}: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )

                # Call retry callback if provided
                if on_retry:
                    on_retry(attempt + 1, e)

                await asyncio.sleep(delay)

    # All retries exhausted
    if fallback_response is not None:
        logger.info(f"Using fallback response for {func.__name__}")
        return fallback_response

    if last_exception:
        raise last_exception

    raise RuntimeError(f"Unexpected state in retry logic for {func.__name__}")


def with_retry(
    config: RetryConfig | None = None,
    fallback_response: Any = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to add retry logic to a function.

    Args:
        config: Retry configuration
        fallback_response: Value to return if all retries fail

    Returns:
        Decorated function with retry logic
    """
    config = config or DEFAULT_RETRY_CONFIG

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await execute_with_retry(
                func,
                *args,
                config=config,
                fallback_response=fallback_response,
                **kwargs,
            )

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return asyncio.run(
                execute_with_retry(
                    func,
                    *args,
                    config=config,
                    fallback_response=fallback_response,
                    **kwargs,
                )
            )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class RetryableMixin:
    """
    Mixin class that adds retry capability to any class.

    Usage:
        class MyAgent(RetryableMixin):
            async def call_llm(self, prompt):
                return await self.with_retry(
                    self._do_call_llm,
                    prompt,
                    fallback_response="Sorry, I couldn't process that."
                )
    """

    _retry_config: RetryConfig = DEFAULT_RETRY_CONFIG

    async def with_retry(
        self,
        func: Callable[P, T],
        *args: P.args,
        fallback_response: T | None = None,
        **kwargs: P.kwargs,
    ) -> T:
        """Execute a method with retry logic."""
        return await execute_with_retry(
            func,
            *args,
            config=self._retry_config,
            fallback_response=fallback_response,
            **kwargs,
        )

    def set_retry_config(self, config: RetryConfig) -> None:
        """Update retry configuration."""
        self._retry_config = config
