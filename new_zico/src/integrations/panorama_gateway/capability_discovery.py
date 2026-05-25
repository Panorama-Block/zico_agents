"""Capability availability lookup (card #69).

Wraps the backend `GET /v1/capability/_discovery` endpoint owned by the
`@panorama/capability` shared package (card #207). Returns the discovery
snapshot that agents should consult **before** proposing a state-mutating
action — so they only ever suggest capabilities the BE confirms are healthy.

The endpoint response shape (`AvailabilityMap`) is defined in
`shared/capability/availability.types.ts`.

A 30-second in-process cache is layered on top to keep token cost low when
several agents fan out within the same turn. The TTL matches the
`cacheTtlSeconds` the BE handler announces.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------


_CACHE_TTL_SECONDS = 30
_cache_lock = threading.Lock()
_cache: Dict[Optional[int], "_CacheEntry"] = {}


class _CacheEntry:
    __slots__ = ("payload", "expires_at")

    def __init__(self, payload: Dict[str, Any], ttl_seconds: float) -> None:
        self.payload = payload
        self.expires_at = time.monotonic() + ttl_seconds


def _cached(chain_id: Optional[int]) -> Optional[Dict[str, Any]]:
    with _cache_lock:
        entry = _cache.get(chain_id)
        if entry is None or entry.expires_at <= time.monotonic():
            return None
        return entry.payload


def _store(chain_id: Optional[int], payload: Dict[str, Any], ttl_seconds: float) -> None:
    with _cache_lock:
        _cache[chain_id] = _CacheEntry(payload, ttl_seconds)


def clear_cache() -> None:
    """Drop every cached discovery snapshot. Used by tests and on-demand refresh."""

    with _cache_lock:
        _cache.clear()


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------


_DEFAULT_TIMEOUT = 10.0


class DiscoveryFetchError(RuntimeError):
    """Raised when the discovery endpoint returns non-200 or unparseable JSON."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _base_url() -> str:
    url = os.getenv("PANORAMA_CAPABILITY_BASE_URL")
    if not url:
        raise RuntimeError(
            "PANORAMA_CAPABILITY_BASE_URL is required to call /v1/capability/_discovery"
        )
    return url.rstrip("/")


def _http_get_discovery(
    chain_id: Optional[int],
    *,
    client: Optional[httpx.Client] = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    url = f"{_base_url()}/v1/capability/_discovery"
    params = {"chainId": str(chain_id)} if chain_id is not None else None

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=timeout)
    try:
        response = client.get(url, params=params)
    finally:
        if owns_client:
            client.close()

    if response.status_code != 200:
        raise DiscoveryFetchError(
            f"discovery returned HTTP {response.status_code}",
            status_code=response.status_code,
        )
    try:
        body = response.json()
    except ValueError as err:
        raise DiscoveryFetchError("discovery response was not valid JSON") from err

    # The handler wraps the AvailabilityMap in CapabilitySuccessResponse — unwrap.
    if isinstance(body, dict) and body.get("status") == "success" and "data" in body:
        return body["data"]
    return body


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover_capabilities(
    chain_id: Optional[int] = None,
    *,
    force_refresh: bool = False,
    client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """Return the discovery snapshot, hitting the cache when fresh.

    Args:
        chain_id: optional EIP-155 id; when set, the BE filters the snapshot.
        force_refresh: bypass the in-process cache and re-hit the BE.
        client: optional httpx.Client (used by tests; production callers omit).

    Returns:
        The `AvailabilityMap` payload as a plain dict:
        `{ capabilities: [...], generatedAt: str, cacheTtlSeconds: int }`.
    """

    if not force_refresh:
        cached = _cached(chain_id)
        if cached is not None:
            return cached

    payload = _http_get_discovery(chain_id, client=client)

    ttl = payload.get("cacheTtlSeconds")
    ttl_seconds = float(ttl) if isinstance(ttl, (int, float)) and ttl > 0 else _CACHE_TTL_SECONDS
    _store(chain_id, payload, ttl_seconds)
    return payload


def list_healthy_providers(
    capability: str, chain_id: int, *, force_refresh: bool = False
) -> List[str]:
    """Convenience: project the discovery snapshot to provider names that report healthy."""

    snapshot = discover_capabilities(chain_id=chain_id, force_refresh=force_refresh)
    healthy: List[str] = []
    for entry in snapshot.get("capabilities", []):
        if entry.get("capability") != capability:
            continue
        by_chain = entry.get("byChain", {}) or {}
        # AvailabilityMap.byChain keys are numeric on the wire, JSON-decoded as str.
        providers = by_chain.get(str(chain_id), [])
        healthy.extend(p["provider"] for p in providers if p.get("healthy"))
    return healthy


# ---------------------------------------------------------------------------
# LangChain Tool wrapper — registrable on any agent
# ---------------------------------------------------------------------------


class DiscoverCapabilitiesInput(BaseModel):
    """Inputs for the `discover_capabilities` LangChain tool."""

    chain_id: Optional[int] = Field(
        default=None,
        description="Optional EIP-155 chain id (e.g. 8453 for Base). Omit for all chains.",
    )
    force_refresh: bool = Field(
        default=False,
        description="Bypass the 30-second in-process cache.",
    )


@tool("discover_capabilities", args_schema=DiscoverCapabilitiesInput)
def discover_capabilities_tool(
    chain_id: Optional[int] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """List capabilities (swap, lending, staking, liquidity, …) and their healthy providers.

    Always call this **before** proposing a state-mutating action so you only
    suggest capabilities the backend confirms are available on the user's chain.

    Returns the raw `AvailabilityMap` so the agent can reason over per-chain
    health, last error, and 95th-percentile latency.
    """

    try:
        return discover_capabilities(chain_id=chain_id, force_refresh=force_refresh)
    except DiscoveryFetchError as err:
        logger.warning("capability discovery failed status=%s", err.status_code)
        return {
            "capabilities": [],
            "generatedAt": None,
            "cacheTtlSeconds": 0,
            "error": str(err),
        }


__all__ = [
    "DiscoveryFetchError",
    "DiscoverCapabilitiesInput",
    "clear_cache",
    "discover_capabilities",
    "discover_capabilities_tool",
    "list_healthy_providers",
]
