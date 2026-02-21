"""
Tiered TTL cache for external API calls (CoinGecko, DefiLlama).

Different data types have different staleness thresholds:
- price:        30 s  (volatile)
- market_cap:  300 s  (5 min)
- tvl:         900 s  (15 min)
- fdv:         300 s  (5 min)
- floor_price:  60 s  (1 min)
- coingecko_id: 86400 s (24 h — IDs never change)
- protocols:   3600 s  (1 h)
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from threading import Lock
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Sentinel for distinguishing "cached None" from "no entry"
_MISSING = object()

TTL_MAP: dict[str, int] = {
    "price": 30,
    "market_cap": 300,
    "tvl": 900,
    "fdv": 300,
    "floor_price": 60,
    "coingecko_id": 86400,
    "protocols": 3600,
    "tradingview": 86400,
}

# How long to cache errors to avoid hammering rate-limited APIs (seconds)
ERROR_TTL: int = 30


class _CachedError:
    """Wrapper so we can store and re-raise cached exceptions."""
    __slots__ = ("exc",)

    def __init__(self, exc: Exception) -> None:
        self.exc = exc


class TieredCache:
    """Thread-safe in-memory cache with per-type TTL."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str, data_type: str) -> Any:
        ttl = TTL_MAP.get(data_type, 60)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return _MISSING
            value, ts = entry
            # Errors use a shorter TTL
            effective_ttl = ERROR_TTL if isinstance(value, _CachedError) else ttl
            if (time.time() - ts) < effective_ttl:
                self._hits += 1
                return value
            self._misses += 1
            return _MISSING

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (value, time.time())

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
            "size": len(self._store),
        }


# Module-level singleton
_cache = TieredCache()


def get_cache() -> TieredCache:
    """Return the module-level cache singleton."""
    return _cache


def cached(data_type: str):
    """
    Decorator that caches the return value using the tiered TTL.

    Cache key is built from function name + positional/keyword arguments.
    Exceptions are cached briefly (ERROR_TTL) to prevent rate-limit storms.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            result = _cache.get(cache_key, data_type)
            if result is not _MISSING:
                if isinstance(result, _CachedError):
                    raise result.exc
                return result
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                _cache.set(cache_key, _CachedError(exc))
                raise
            _cache.set(cache_key, result)
            return result

        # Expose cache bypass for testing
        wrapper.uncached = func  # type: ignore[attr-defined]
        return wrapper

    return decorator
