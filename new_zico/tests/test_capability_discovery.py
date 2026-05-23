"""Tests for src/integrations/panorama_gateway/capability_discovery.py (card #69).

Mocks HTTP via httpx.MockTransport so we exercise the real httpx code path
without hitting the network. Verifies: discovery unwraps CapabilitySuccessResponse,
the 30-second cache returns the same payload until force_refresh, and the
list_healthy_providers projection filters by capability+chain+healthy flag.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx
import pytest

from src.integrations.panorama_gateway import capability_discovery as cd


BASE_URL = "https://capability.test"


def _availability_map_response() -> Dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "capabilities": [
                {
                    "capability": "swap",
                    "byChain": {
                        "8453": [
                            {"provider": "aerodrome", "healthy": True, "latencyP95Ms": 120},
                            {"provider": "uniswap-trading-api", "healthy": False,
                             "lastError": "503 from upstream"},
                        ]
                    },
                },
                {
                    "capability": "staking",
                    "byChain": {
                        "1": [
                            {"provider": "lido", "healthy": True, "latencyP95Ms": 80}
                        ]
                    },
                },
            ],
            "generatedAt": "2026-05-23T20:00:00.000Z",
            "cacheTtlSeconds": 30,
        },
        "traceId": "00000000-0000-4000-8000-000000000001",
    }


class _RequestRecorder:
    def __init__(self, response_body: Dict[str, Any]) -> None:
        self.calls: List[httpx.Request] = []
        self._body = response_body

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return httpx.Response(200, json=self._body)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Reset cache and env before every test so order doesn't leak state."""
    monkeypatch.setenv("PANORAMA_CAPABILITY_BASE_URL", BASE_URL)
    cd.clear_cache()
    yield
    cd.clear_cache()


def _client_with(recorder: _RequestRecorder) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(recorder))


# ---------------------------------------------------------------------------
# Unwrap + cache behavior
# ---------------------------------------------------------------------------


def test_discover_unwraps_capability_success_envelope():
    recorder = _RequestRecorder(_availability_map_response())
    with _client_with(recorder) as client:
        result = cd.discover_capabilities(client=client)

    assert "capabilities" in result
    assert result["generatedAt"] == "2026-05-23T20:00:00.000Z"
    assert "status" not in result, "envelope must be stripped"
    assert len(recorder.calls) == 1


def test_cache_hit_does_not_call_http_again():
    recorder = _RequestRecorder(_availability_map_response())
    with _client_with(recorder) as client:
        cd.discover_capabilities(client=client)
        cd.discover_capabilities(client=client)
        cd.discover_capabilities(client=client)
    assert len(recorder.calls) == 1


def test_force_refresh_bypasses_cache():
    recorder = _RequestRecorder(_availability_map_response())
    with _client_with(recorder) as client:
        cd.discover_capabilities(client=client)
        cd.discover_capabilities(client=client, force_refresh=True)
    assert len(recorder.calls) == 2


def test_cache_is_per_chain_id():
    recorder = _RequestRecorder(_availability_map_response())
    with _client_with(recorder) as client:
        cd.discover_capabilities(chain_id=8453, client=client)
        cd.discover_capabilities(chain_id=1, client=client)
        cd.discover_capabilities(chain_id=8453, client=client)  # cached
    assert len(recorder.calls) == 2


def test_query_param_includes_chain_id_when_supplied():
    recorder = _RequestRecorder(_availability_map_response())
    with _client_with(recorder) as client:
        cd.discover_capabilities(chain_id=8453, client=client)
    assert recorder.calls[0].url.params.get("chainId") == "8453"


def test_no_query_params_when_chain_id_absent():
    recorder = _RequestRecorder(_availability_map_response())
    with _client_with(recorder) as client:
        cd.discover_capabilities(client=client)
    assert "chainId" not in recorder.calls[0].url.params


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_raises_on_non_200():
    def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(cd.DiscoveryFetchError) as exc:
            cd.discover_capabilities(client=client)
    assert exc.value.status_code == 503


def test_raises_on_invalid_json():
    def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(cd.DiscoveryFetchError):
            cd.discover_capabilities(client=client)


def test_missing_base_url_raises_runtime_error(monkeypatch):
    monkeypatch.delenv("PANORAMA_CAPABILITY_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="PANORAMA_CAPABILITY_BASE_URL"):
        cd.discover_capabilities()


# ---------------------------------------------------------------------------
# Projection helper
# ---------------------------------------------------------------------------


def test_list_healthy_providers_filters_unhealthy():
    recorder = _RequestRecorder(_availability_map_response())
    with _client_with(recorder) as client:
        # Prime cache so list_healthy_providers doesn't re-fetch.
        cd.discover_capabilities(chain_id=8453, client=client)
    healthy = cd.list_healthy_providers("swap", 8453)
    assert healthy == ["aerodrome"]


def test_list_healthy_providers_returns_empty_on_unknown_capability():
    recorder = _RequestRecorder(_availability_map_response())
    with _client_with(recorder) as client:
        cd.discover_capabilities(chain_id=8453, client=client)
    assert cd.list_healthy_providers("bridge", 8453) == []


# ---------------------------------------------------------------------------
# LangChain Tool wrapper
# ---------------------------------------------------------------------------


def test_tool_wrapper_returns_discovery_payload(monkeypatch):
    def fake_discover(chain_id=None, force_refresh=False, client=None):
        return {"capabilities": [], "generatedAt": "now", "cacheTtlSeconds": 30}

    monkeypatch.setattr(cd, "discover_capabilities", fake_discover)
    result = cd.discover_capabilities_tool.invoke({"chain_id": 8453})
    assert result["generatedAt"] == "now"


def test_tool_wrapper_swallows_fetch_error_and_returns_empty(monkeypatch):
    def explode(chain_id=None, force_refresh=False, client=None):
        raise cd.DiscoveryFetchError("boom", status_code=500)

    monkeypatch.setattr(cd, "discover_capabilities", explode)
    result = cd.discover_capabilities_tool.invoke({})
    assert result["capabilities"] == []
    assert result["error"].startswith("boom") or "500" in result["error"]
