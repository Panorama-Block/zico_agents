"""
Rate Limiting Configuration using SlowAPI.

Provides rate limiting for FastAPI endpoints to prevent abuse.
"""

import os
from typing import Callable

from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _get_identifier(request: Request) -> str:
    """
    Get identifier for rate limiting.

    Uses X-Forwarded-For header if behind a proxy,
    otherwise falls back to remote address.
    Also considers user_id from query params or body if available.
    """
    # Try to get user_id for more granular limiting
    user_id = request.query_params.get("user_id")
    if user_id and user_id != "anonymous":
        return f"user:{user_id}"

    # Fall back to IP-based limiting
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    return get_remote_address(request)


# Create global limiter instance
limiter = Limiter(
    key_func=_get_identifier,
    default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "100/minute")],
)


def setup_rate_limiter(app: FastAPI) -> None:
    """
    Configure rate limiting on a FastAPI application.

    Args:
        app: FastAPI application instance
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def limit_chat(func: Callable) -> Callable:
    """
    Rate limit decorator for chat endpoints.

    Default: 30 requests per minute.
    """
    limit = os.getenv("RATE_LIMIT_CHAT", "30/minute")
    return limiter.limit(limit)(func)


def limit_stream(func: Callable) -> Callable:
    """
    Rate limit decorator for streaming endpoints.

    Default: 10 requests per minute (streaming is more resource-intensive).
    """
    limit = os.getenv("RATE_LIMIT_STREAM", "10/minute")
    return limiter.limit(limit)(func)


def limit_health(func: Callable) -> Callable:
    """
    Rate limit decorator for health check endpoints.

    Default: 100 requests per minute.
    """
    limit = os.getenv("RATE_LIMIT_HEALTH", "100/minute")
    return limiter.limit(limit)(func)


def limit_custom(limit_string: str) -> Callable:
    """
    Create a custom rate limit decorator.

    Args:
        limit_string: Rate limit string (e.g., "10/minute", "100/hour")

    Returns:
        Decorator function
    """
    return limiter.limit(limit_string)
