"""
Infrastructure Module - Cross-cutting concerns.

This module provides:
- Logging: Structured logging with color support
- Rate Limiting: API rate limiting with SlowAPI
- Metrics: Prometheus metrics for observability
- Retry: Retry utilities with exponential backoff
"""

from .logging import setup_logging, get_logger
from .retry import execute_with_retry, RetryConfig

try:
    from .rate_limiter import limiter, setup_rate_limiter, limit_chat, limit_stream
except Exception:  # pragma: no cover - optional in minimal test/runtime environments.
    limiter = None  # type: ignore[assignment]
    setup_rate_limiter = None  # type: ignore[assignment]
    limit_chat = None  # type: ignore[assignment]
    limit_stream = None  # type: ignore[assignment]

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    # Rate limiting
    "limiter",
    "setup_rate_limiter",
    "limit_chat",
    "limit_stream",
    # Retry
    "execute_with_retry",
    "RetryConfig",
]
