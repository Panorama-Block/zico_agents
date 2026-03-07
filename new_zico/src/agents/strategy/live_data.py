"""Redis-backed live-data adapters for strategy enrichment."""

from __future__ import annotations

import logging
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Callable

import requests

from src.infrastructure.redis_cache import RedisJSONCache

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter
except Exception:  # pragma: no cover - metric dependency may be unavailable at runtime.
    Counter = None  # type: ignore[assignment]

_DEFI_LLAMA_PROTOCOL = "https://api.llama.fi/protocol"
_DEFI_LLAMA_CHAINS = "https://api.llama.fi/v2/chains"
_DEFI_LLAMA_YIELDS = "https://yields.llama.fi/pools"
_TIMEOUT = 8
_HTTP_RETRIES = 3
_RETRY_BASE_SLEEP = 0.25

_TTL = int(os.getenv("STRATEGY_LIVE_DATA_TTL_SEC", "120"))
_STALE_TTL = int(os.getenv("STRATEGY_LIVE_DATA_STALE_TTL_SEC", "600"))
_ERROR_TTL = int(os.getenv("STRATEGY_LIVE_DATA_ERROR_TTL_SEC", "30"))
_MICRO_TTL = 3
_MICRO_CACHE: dict[str, tuple[Any, float]] = {}
_CACHE = RedisJSONCache.instance()

_CB_FAILURE_THRESHOLD = 3
_CB_WINDOW_SEC = 120
_CB_COOLDOWN_SEC = 60
_DEFAULT_NETWORK = (os.getenv("STRATEGY_DEFAULT_NETWORK", "avalanche") or "avalanche").strip().lower()
_SUPPORTED_NETWORKS = {"avalanche", "base"}
_NETWORK_CHAIN_LABELS: dict[str, dict[str, Any]] = {
    "avalanche": {"name": "Avalanche", "aliases": ("avalanche", "avax"), "registry": "strategy_registry.avalanche.json"},
    "base": {"name": "Base", "aliases": ("base",), "registry": "strategy_registry.base.json"},
}
_PROTOCOL_API_ENDPOINTS: dict[str, str] = {
    "Morpho Blue": "https://api.morpho.org/markets",
    "Aerodrome": "https://api.aerodrome.finance",
    "Beefy Finance": "https://api.beefy.finance/apy",
    "Yearn": "https://api.yearn.finance",
    "Ondo Finance": "https://api.ondo.finance",
}

_PROTOCOL_MAP: dict[str, dict[str, Any]] = {
    "OpenTrade": {
        "protocol_slug": "opentrade",
        "project_aliases_exact": ["opentrade"],
        "project_aliases_contains": ["opentrade"],
    },
    "Securitize": {
        "protocol_slug": "securitize",
        "project_aliases_exact": ["securitize"],
        "project_aliases_contains": ["securitize"],
    },
    "Centrifuge Protocol": {
        "protocol_slug": "centrifuge",
        "project_aliases_exact": ["centrifuge"],
        "project_aliases_contains": ["centrifuge"],
    },
    "Euler V2": {
        "protocol_slug": "euler-v2",
        "project_aliases_exact": ["euler-v2"],
        "project_aliases_contains": ["euler"],
    },
    "MEV Capital": {
        "protocol_slug": "mev-capital",
        "project_aliases_exact": ["mev-capital"],
        "project_aliases_contains": ["mev-capital", "mev"],
    },
    "Re7 Labs": {
        "protocol_slug": "re7-labs",
        "project_aliases_exact": ["re7-labs"],
        "project_aliases_contains": ["re7"],
    },
    "Varlamore Capital": {
        "protocol_slug": "varlamore-capital",
        "project_aliases_exact": ["varlamore-capital"],
        "project_aliases_contains": ["varlamore"],
    },
    "Hypha": {
        "protocol_slug": "hypha",
        "project_aliases_exact": ["hypha"],
        "project_aliases_contains": ["hypha"],
    },
    "Spark": {
        "protocol_slug": "spark-savings",
        "project_aliases_exact": ["spark-savings"],
        "project_aliases_contains": ["spark"],
    },
    "XSY": {
        "protocol_slug": "xsy",
        "project_aliases_exact": ["xsy"],
        "project_aliases_contains": ["xsy"],
    },
    "LFJ": {
        "protocol_slug": "joe-v2",
        "project_aliases_exact": ["joe-v2", "joe-v2.1", "joe-v2.2", "joe-lend"],
        "project_aliases_contains": ["joe", "lfj", "trader-joe"],
    },
    "Blackhole": {
        "protocol_slug": "blackhole-amm",
        "project_aliases_exact": ["blackhole-amm", "blackhole-clmm"],
        "project_aliases_contains": ["blackhole"],
    },
    "Pharaoh Exchange": {
        "protocol_slug": "pharaoh-v3",
        "project_aliases_exact": ["pharaoh-v3"],
        "project_aliases_contains": ["pharaoh"],
    },
    "K3 Capital": {
        "protocol_slug": "k3-capital",
        "project_aliases_exact": ["k3-capital"],
        "project_aliases_contains": ["k3"],
    },
    "Avant Protocol": {
        "protocol_slug": "avant-protocol",
        "project_aliases_exact": ["avant-protocol"],
        "project_aliases_contains": ["avant"],
    },
    "Morpho Blue": {
        "protocol_slug": "morpho-blue",
        "project_aliases_exact": ["morpho-blue", "morpho"],
        "project_aliases_contains": ["morpho"],
    },
    "Ondo Finance": {
        "protocol_slug": "ondo-finance",
        "project_aliases_exact": ["ondo-finance", "ondo"],
        "project_aliases_contains": ["ondo"],
    },
    "Aerodrome": {
        "protocol_slug": "aerodrome-slipstream",
        "project_aliases_exact": ["aerodrome-slipstream", "aerodrome"],
        "project_aliases_contains": ["aerodrome"],
    },
    "Beefy Finance": {
        "protocol_slug": "beefy",
        "project_aliases_exact": ["beefy"],
        "project_aliases_contains": ["beefy"],
    },
    "Yearn": {
        "protocol_slug": "yearn-finance",
        "project_aliases_exact": ["yearn-finance", "yearn"],
        "project_aliases_contains": ["yearn"],
    },
    "Rocket Pool": {
        "protocol_slug": "rocket-pool",
        "project_aliases_exact": ["rocket-pool"],
        "project_aliases_contains": ["rocket"],
    },
    "Uniswap V3": {
        "protocol_slug": "uniswap-v3",
        "project_aliases_exact": ["uniswap-v3", "uniswap"],
        "project_aliases_contains": ["uniswap"],
    },
    "Perpetual Markets": {
        "protocol_slug": "gmx",
        "project_aliases_exact": ["gmx", "kwenta", "hyperliquid"],
        "project_aliases_contains": ["perp", "gmx", "hyperliquid"],
    },
    "Ethena": {
        "protocol_slug": "ethena",
        "project_aliases_exact": ["ethena"],
        "project_aliases_contains": ["ethena"],
    },
}

if Counter:
    _METRIC_CACHE_HITS = Counter(
        "strategy_live_data_cache_hits_total",
        "Total strategy live-data cache hits.",
    )
    _METRIC_FETCH_FAILURES = Counter(
        "strategy_live_data_fetch_failures_total",
        "Total strategy live-data upstream fetch failures.",
        ["source"],
    )
    _METRIC_FALLBACKS = Counter(
        "strategy_live_data_fallback_total",
        "Total strategy live-data fallback responses.",
        ["source"],
    )
else:  # pragma: no cover - used only when metrics package is missing.
    _METRIC_CACHE_HITS = None
    _METRIC_FETCH_FAILURES = None
    _METRIC_FALLBACKS = None


def _now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


def _micro_get(key: str) -> Any:
    entry = _MICRO_CACHE.get(key)
    if not entry:
        return None
    value, ts = entry
    if (time.time() - ts) > _MICRO_TTL:
        return None
    return value


def _micro_set(key: str, value: Any) -> None:
    _MICRO_CACHE[key] = (value, time.time())


def _metric_inc(metric, **labels: str) -> None:
    if metric is None:
        return
    try:
        if labels:
            metric.labels(**labels).inc()
        else:
            metric.inc()
    except Exception:
        return


def _slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")


def _normalize_network(network: str | None) -> str:
    normalized = (network or _DEFAULT_NETWORK).strip().lower()
    if normalized in _SUPPORTED_NETWORKS:
        return normalized
    return _DEFAULT_NETWORK


def _build_cache_key(category: str, protocols: List[str], network: str = _DEFAULT_NETWORK) -> str:
    normalized_network = _normalize_network(network)
    normalized_protocols = [_slugify(p) for p in protocols if p]
    normalized_protocols = sorted(set(normalized_protocols))
    protocol_part = "|".join(normalized_protocols) if normalized_protocols else "none"
    return f"live:{normalized_network}:{_slugify(category or 'unknown')}:{protocol_part}"


def _is_cb_open(source: str) -> bool:
    return _CACHE.exists(f"cb:{source}:cooldown")


def _record_cb_failure(source: str) -> None:
    failures = _CACHE.incr(f"cb:{source}:failures", ttl=_CB_WINDOW_SEC)
    if failures >= _CB_FAILURE_THRESHOLD:
        _CACHE.set_json(f"cb:{source}:cooldown", {"until": _now_iso()}, ttl=_CB_COOLDOWN_SEC)


def _record_cb_success(source: str) -> None:
    # Soft reset: overwriting with low TTL is enough to make the window pass quickly.
    _CACHE.set_json(f"cb:{source}:failures", 0, ttl=1)


def _http_get_json(url: str, source: str) -> Any:
    cache_key = f"http:{_slugify(url)}"
    cached = _CACHE.get_json(cache_key)
    if cached is not None:
        _metric_inc(_METRIC_CACHE_HITS)
        return cached

    if _is_cb_open(source):
        raise RuntimeError(f"circuit_open:{source}")

    start = time.perf_counter()
    last_exc: Exception | None = None
    for attempt in range(_HTTP_RETRIES):
        try:
            response = requests.get(url, timeout=_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            _CACHE.set_json(cache_key, payload, ttl=_TTL)
            _record_cb_success(source)
            logger.info(
                "strategy_live_data_fetch_ok source=%s url=%s attempt=%s latency_ms=%s",
                source,
                url,
                attempt + 1,
                int((time.perf_counter() - start) * 1000),
            )
            return payload
        except Exception as exc:
            last_exc = exc
            if attempt < (_HTTP_RETRIES - 1):
                time.sleep(_RETRY_BASE_SLEEP * (2**attempt))
            continue

    _record_cb_failure(source)
    _metric_inc(_METRIC_FETCH_FAILURES, source=source)
    logger.warning(
        "strategy_live_data_fetch_failed source=%s url=%s error=%s",
        source,
        url,
        last_exc,
    )
    raise RuntimeError(f"fetch_failed:{source}") from last_exc


def _fallback(source: str, warning: str) -> Dict[str, Any]:
    return {
        "apy": None,
        "tvl": None,
        "capacity": "unknown",
        "risk_flags": [warning],
        "as_of": _now_iso(),
        "source": source,
        "freshness": "stale",
        "warning": warning,
        "confidence": "low",
    }


def _defillama_protocol_slug(protocol: str) -> str:
    mapped = _PROTOCOL_MAP.get(protocol or "", {})
    if mapped.get("protocol_slug"):
        return str(mapped["protocol_slug"])
    return protocol.lower().replace(" protocol", "").replace(" ", "-")


def _load_static_apy_defaults(network: str = _DEFAULT_NETWORK) -> Dict[str, float]:
    normalized_network = _normalize_network(network)
    registry_name = str(_NETWORK_CHAIN_LABELS.get(normalized_network, {}).get("registry") or "strategy_registry.avalanche.json")
    registry_path = Path(__file__).resolve().parent / registry_name
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, list):
        return {}
    by_protocol: dict[str, list[float]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        assumptions = entry.get("simulation_assumptions") or {}
        base_apy = assumptions.get("base_apy")
        protocols = entry.get("protocols") or []
        if not isinstance(base_apy, (int, float)) or not isinstance(protocols, list):
            continue
        for protocol in protocols:
            if isinstance(protocol, str) and protocol:
                by_protocol.setdefault(protocol, []).append(float(base_apy))
    return {
        protocol: (sum(values) / len(values))
        for protocol, values in by_protocol.items()
        if values
    }


_STATIC_APY_DEFAULTS_BY_NETWORK: Dict[str, Dict[str, float]] = {}


def _static_defaults(network: str) -> Dict[str, float]:
    normalized_network = _normalize_network(network)
    if normalized_network not in _STATIC_APY_DEFAULTS_BY_NETWORK:
        _STATIC_APY_DEFAULTS_BY_NETWORK[normalized_network] = _load_static_apy_defaults(normalized_network)
    return _STATIC_APY_DEFAULTS_BY_NETWORK[normalized_network]


def _extract_chain_tvl(data: Dict[str, Any], network: str) -> float | None:
    normalized_network = _normalize_network(network)
    aliases = tuple(str(v).lower() for v in (_NETWORK_CHAIN_LABELS.get(normalized_network, {}).get("aliases") or (normalized_network,)))
    tvl = data.get("tvl") if isinstance(data, dict) else None
    chain_tvls = data.get("chainTvls") if isinstance(data, dict) else None
    chain_tvl = None
    if isinstance(chain_tvls, dict):
        for key, value in chain_tvls.items():
            key_l = str(key).lower()
            if any(alias in key_l for alias in aliases):
                if isinstance(value, dict):
                    chain_tvl = value.get("tvl")
                elif isinstance(value, (int, float)):
                    chain_tvl = value
                break
    raw_tvl = chain_tvl if chain_tvl is not None else tvl
    return float(raw_tvl) if isinstance(raw_tvl, (int, float)) else None


def _fetch_protocol_stats(protocol: str, network: str) -> Dict[str, Any]:
    slug = _defillama_protocol_slug(protocol)
    url = f"{_DEFI_LLAMA_PROTOCOL}/{slug}"
    data = _http_get_json(url, source="defillama_protocol")
    tvl = _extract_chain_tvl(data, network) if isinstance(data, dict) else None
    return {
        "apy": None,
        "tvl": tvl,
        "capacity": "ok" if tvl is not None else "unknown",
        "risk_flags": [],
        "as_of": _now_iso(),
        "source": "defillama",
        "freshness": "fresh",
        "warning": None,
        "confidence": "medium",
    }


def _defillama_aliases(protocol: str) -> set[str]:
    mapped = _PROTOCOL_MAP.get(protocol or "", {})
    aliases = {str(a).lower() for a in (mapped.get("project_aliases_exact") or [])}
    if not aliases:
        aliases.add(_slugify(protocol))
    aliases.add(_slugify(protocol).replace("-protocol", ""))
    return aliases


def _defillama_alias_fragments(protocol: str) -> set[str]:
    mapped = _PROTOCOL_MAP.get(protocol or "", {})
    frags = {str(a).lower() for a in (mapped.get("project_aliases_contains") or [])}
    frags.add(_slugify(protocol).replace("-protocol", ""))
    return {f for f in frags if f}


def _project_matches_protocol(project: str, protocol: str) -> bool:
    name = (project or "").lower()
    if not name:
        return False
    exact = _defillama_aliases(protocol)
    if name in exact:
        return True
    fragments = _defillama_alias_fragments(protocol)
    return any(fragment in name for fragment in fragments)


def _pool_apy(pool: Dict[str, Any]) -> float | None:
    apy = pool.get("apy")
    if isinstance(apy, (int, float)):
        return float(apy)
    apy_base = pool.get("apyBase")
    apy_reward = pool.get("apyReward")
    if isinstance(apy_base, (int, float)) and isinstance(apy_reward, (int, float)):
        return float(apy_base) + float(apy_reward)
    return None


def _iter_numeric_values(payload: Any, key_hints: tuple[str, ...]) -> list[float]:
    values: list[float] = []
    key_tokens = tuple(k.lower() for k in key_hints)
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_l = str(key).lower()
            if any(token in key_l for token in key_tokens) and isinstance(value, (int, float)):
                values.append(float(value))
            values.extend(_iter_numeric_values(value, key_hints))
    elif isinstance(payload, list):
        for item in payload:
            values.extend(_iter_numeric_values(item, key_hints))
    return values


def _fetch_protocol_api_fallback(protocol: str) -> Dict[str, Any] | None:
    url = _PROTOCOL_API_ENDPOINTS.get(protocol)
    if not url:
        return None
    try:
        payload = _http_get_json(url, source=f"{_slugify(protocol)}_api")
    except Exception:
        return None

    apy_candidates = _iter_numeric_values(payload, ("apy", "apr", "rate", "yield"))
    tvl_candidates = _iter_numeric_values(payload, ("tvl", "liquidity", "aum", "assets"))
    if not apy_candidates:
        return None

    apy = max(apy_candidates)
    if apy > 1:
        apy = apy / 100.0
    tvl = max(tvl_candidates) if tvl_candidates else None
    return {
        "apy": float(apy),
        "tvl": float(tvl) if isinstance(tvl, (int, float)) else None,
        "capacity": "ok",
        "risk_flags": ["APY derived from protocol API payload heuristics."],
        "as_of": _now_iso(),
        "source": "protocol_api",
        "freshness": "fresh",
        "warning": None,
        "confidence": "medium",
    }


def _fetch_pool_apy(protocol: str, network: str) -> Dict[str, Any] | None:
    normalized_network = _normalize_network(network)
    chain_name = str(_NETWORK_CHAIN_LABELS.get(normalized_network, {}).get("name") or normalized_network.title())
    aliases = tuple(str(v).lower() for v in (_NETWORK_CHAIN_LABELS.get(normalized_network, {}).get("aliases") or (normalized_network,)))
    payload = _http_get_json(_DEFI_LLAMA_YIELDS, source="defillama_yields")
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return None
    chain_matches: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        project = str(row.get("project") or "").lower()
        chain = str(row.get("chain") or "").lower()
        if not _project_matches_protocol(project, protocol):
            continue
        if any(alias in chain for alias in aliases):
            chain_matches.append(row)

    if chain_matches:
        chain_matches.sort(key=lambda p: float(p.get("tvlUsd") or 0), reverse=True)
        top = chain_matches[0]
        apy = _pool_apy(top)
        if apy is not None:
            return {
                "apy": apy / 100.0 if apy > 1 else apy,
                "tvl": float(top.get("tvlUsd") or 0) if top.get("tvlUsd") is not None else None,
                "capacity": "ok",
                "risk_flags": [],
                "as_of": _now_iso(),
                "source": "defillama",
                "freshness": "fresh",
                "warning": None,
                "confidence": "high",
            }

    # Protocol-level fallback from global pools average when chain-specific pool is unavailable.
    protocol_rows = [
        row for row in rows
        if isinstance(row, dict)
        and _project_matches_protocol(str(row.get("project") or "").lower(), protocol)
        and _pool_apy(row) is not None
    ]
    if protocol_rows:
        weighted_numerator = 0.0
        weighted_denominator = 0.0
        for row in protocol_rows:
            apy = _pool_apy(row)
            if apy is None:
                continue
            tvl = float(row.get("tvlUsd") or 1.0)
            weighted_numerator += (apy * max(tvl, 1.0))
            weighted_denominator += max(tvl, 1.0)
        if weighted_denominator > 0:
            inferred = weighted_numerator / weighted_denominator
            total_tvl = sum(float(r.get("tvlUsd") or 0) for r in protocol_rows)
            return {
                "apy": inferred / 100.0 if inferred > 1 else inferred,
                "tvl": total_tvl or None,
                "capacity": "ok",
                "risk_flags": [f"APY inferred from protocol-level pools, {chain_name}-specific pool unavailable."],
                "as_of": _now_iso(),
                "source": "protocol_fallback",
                "freshness": "fresh",
                "warning": f"{chain_name}-specific APY not found; using protocol-level inferred APY.",
                "confidence": "medium",
            }
    return None


def _static_protocol_fallback(protocols: List[str], category: str, network: str) -> Dict[str, Any]:
    defaults = _static_defaults(network)
    for protocol in protocols:
        base_apy = defaults.get(protocol)
        if isinstance(base_apy, (int, float)):
            warning = f"Using static APY fallback for {protocol}."
            _metric_inc(_METRIC_FALLBACKS, source="static")
            return {
                "apy": float(base_apy),
                "tvl": None,
                "capacity": "unknown",
                "risk_flags": [warning],
                "as_of": _now_iso(),
                "source": "static_assumption",
                "freshness": "stale",
                "warning": warning,
                "confidence": "low",
            }
    _metric_inc(_METRIC_FALLBACKS, source="static")
    return _fallback("static_assumption", f"No static APY fallback found for category '{category}'.")


def _resolve_with_sources(protocol: str, network: str) -> Dict[str, Any]:
    pooled = _fetch_pool_apy(protocol, network)
    if pooled:
        return pooled
    protocol_api = _fetch_protocol_api_fallback(protocol)
    if protocol_api:
        return protocol_api
    stats = _fetch_protocol_stats(protocol, network)
    if stats.get("apy") is not None or stats.get("tvl") is not None:
        return stats
    return _static_protocol_fallback([protocol], "unknown", network)


def _adapter_opentrade(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("OpenTrade", network)


def _adapter_securitize(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Securitize", network)


def _adapter_centrifuge(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Centrifuge Protocol", network)


def _adapter_euler_v2(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Euler V2", network)


def _adapter_mev_capital(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("MEV Capital", network)


def _adapter_re7_labs(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Re7 Labs", network)


def _adapter_varlamore(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Varlamore Capital", network)


def _adapter_hypha(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Hypha", network)


def _adapter_spark(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Spark", network)


def _adapter_xsy(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("XSY", network)


def _adapter_lfj(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("LFJ", network)


def _adapter_blackhole(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Blackhole", network)


def _adapter_pharaoh(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Pharaoh Exchange", network)


def _adapter_k3(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("K3 Capital", network)


def _adapter_avant(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Avant Protocol", network)


def _adapter_morpho_blue(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Morpho Blue", network)


def _adapter_ondo(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Ondo Finance", network)


def _adapter_aerodrome(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Aerodrome", network)


def _adapter_beefy(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Beefy Finance", network)


def _adapter_yearn(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Yearn", network)


def _adapter_rocket_pool(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Rocket Pool", network)


def _adapter_uniswap_v3(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Uniswap V3", network)


def _adapter_perpetual_markets(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Perpetual Markets", network)


def _adapter_ethena(network: str) -> Dict[str, Any]:
    return _resolve_with_sources("Ethena", network)


_PROTOCOL_ADAPTERS: dict[str, Callable[[str], Dict[str, Any]]] = {
    "OpenTrade": _adapter_opentrade,
    "Securitize": _adapter_securitize,
    "Centrifuge Protocol": _adapter_centrifuge,
    "Euler V2": _adapter_euler_v2,
    "MEV Capital": _adapter_mev_capital,
    "Re7 Labs": _adapter_re7_labs,
    "Varlamore Capital": _adapter_varlamore,
    "Hypha": _adapter_hypha,
    "Spark": _adapter_spark,
    "XSY": _adapter_xsy,
    "LFJ": _adapter_lfj,
    "Blackhole": _adapter_blackhole,
    "Pharaoh Exchange": _adapter_pharaoh,
    "K3 Capital": _adapter_k3,
    "Avant Protocol": _adapter_avant,
    "Morpho Blue": _adapter_morpho_blue,
    "Ondo Finance": _adapter_ondo,
    "Aerodrome": _adapter_aerodrome,
    "Beefy Finance": _adapter_beefy,
    "Yearn": _adapter_yearn,
    "Rocket Pool": _adapter_rocket_pool,
    "Uniswap V3": _adapter_uniswap_v3,
    "Perpetual Markets": _adapter_perpetual_markets,
    "Ethena": _adapter_ethena,
}


def _confidence_rank(value: str | None) -> int:
    rank = {"low": 1, "medium": 2, "high": 3}
    return rank.get((value or "").lower(), 0)


def _select_best_result(results: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not results:
        return None
    sorted_results = sorted(
        results,
        key=lambda r: (
            1 if r.get("apy") is not None else 0,
            1 if r.get("freshness") == "fresh" else 0,
            _confidence_rank(str(r.get("confidence"))),
            float(r.get("apy") or 0.0),
            float(r.get("tvl") or 0.0),
        ),
        reverse=True,
    )
    return sorted_results[0]


def _resolve_protocols(protocols: List[str], category: str, network: str) -> Dict[str, Any]:
    if not protocols:
        return _static_protocol_fallback([], category, network)
    results: List[Dict[str, Any]] = []
    for protocol in protocols:
        adapter = _PROTOCOL_ADAPTERS.get(protocol)
        try:
            result = adapter(network) if adapter else _resolve_with_sources(protocol, network)
        except Exception as exc:
            logger.info("Protocol adapter fallback for %s: %s", protocol, exc)
            result = _static_protocol_fallback([protocol], category, network)
        if isinstance(result, dict):
            tagged = dict(result)
            tagged["protocol"] = protocol
            results.append(tagged)

    best = _select_best_result(results)
    if best is None:
        return _static_protocol_fallback(protocols, category, network)
    if len(results) > 1:
        other_protocols = [str(r.get("protocol")) for r in results if r.get("protocol") != best.get("protocol")]
        if other_protocols:
            flags = list(best.get("risk_flags") or [])
            flags.append(
                f"Selected best live data from {best.get('protocol')} among {len(results)} protocol adapters."
            )
            best["risk_flags"] = flags
    return best


def _with_stale_fallback(cache_key: str, fetcher, category: str, protocols: List[str], network: str) -> Dict[str, Any]:
    now = time.time()
    redis_payload = _CACHE.get_json(cache_key)
    stale_candidate = None
    if isinstance(redis_payload, dict):
        cached_at = float(redis_payload.get("_cached_at", 0) or 0)
        age = now - cached_at if cached_at else (_TTL + 1)
        if age <= _TTL:
            _metric_inc(_METRIC_CACHE_HITS)
            payload = dict(redis_payload.get("payload") or {})
            payload["freshness"] = "fresh"
            _micro_set(cache_key, payload)
            logger.info("strategy_live_data_cache_hit key=%s age_s=%s", cache_key, int(age))
            return payload
        if age <= _STALE_TTL:
            stale_candidate = dict(redis_payload.get("payload") or {})

    error_payload = _CACHE.get_json(f"{cache_key}:error")
    if isinstance(error_payload, dict) and error_payload.get("__error__"):
        if stale_candidate:
            stale_candidate["freshness"] = "stale"
            stale_candidate["warning"] = stale_candidate.get("warning") or "Serving stale cached live data due to upstream errors."
            logger.info("strategy_live_data_stale_hit key=%s reason=negative_cache", cache_key)
            return stale_candidate
        return _static_protocol_fallback(protocols, category, network)

    try:
        result = fetcher()
        _CACHE.set_json(cache_key, {"payload": result, "_cached_at": now}, ttl=_STALE_TTL)
        _micro_set(cache_key, result)
        return result
    except Exception as exc:
        _CACHE.set_error(f"{cache_key}:error", {"error": str(exc), "as_of": _now_iso()}, ttl=_ERROR_TTL)
        if stale_candidate:
            stale_candidate["freshness"] = "stale"
            stale_candidate["warning"] = stale_candidate.get("warning") or "Serving stale cached live data due to upstream errors."
            logger.info("strategy_live_data_stale_hit key=%s reason=fetch_failure", cache_key)
            _metric_inc(_METRIC_FALLBACKS, source="stale_cache")
            return stale_candidate
        raise


def rwa_adapter(protocols: List[str], network: str) -> Dict[str, Any]:
    try:
        stats = _resolve_protocols(protocols, "rwa", network)
        if stats.get("tvl") is None:
            stats["risk_flags"].append("No live TVL for RWA protocol.")
        return stats
    except Exception as exc:
        logger.info("RWA adapter fallback for protocols=%s: %s", protocols, exc)
        return _static_protocol_fallback(protocols, "rwa", network)


def lending_adapter(protocols: List[str], network: str) -> Dict[str, Any]:
    try:
        return _resolve_protocols(protocols, "lending", network)
    except Exception as exc:
        logger.info("Lending adapter fallback for protocols=%s: %s", protocols, exc)
        return _static_protocol_fallback(protocols, "lending", network)


def lp_adapter(protocols: List[str], network: str) -> Dict[str, Any]:
    normalized_network = _normalize_network(network)
    chain_name = str(_NETWORK_CHAIN_LABELS.get(normalized_network, {}).get("name") or normalized_network.title())
    try:
        live = _resolve_protocols(protocols, "lp", normalized_network)
        if live.get("apy") is not None:
            return live
        chain_data = _http_get_json(_DEFI_LLAMA_CHAINS, source="defillama_chains")
        chain_row = None
        if isinstance(chain_data, list):
            chain_row = next((c for c in chain_data if str(c.get("name", "")).lower() == chain_name.lower()), None)
        return {
            "apy": None,
            "tvl": float(chain_row.get("tvl") or 0) if chain_row else None,
            "capacity": "ok" if chain_row else "unknown",
            "risk_flags": [],
            "as_of": _now_iso(),
            "source": "defillama_chains",
            "freshness": "fresh" if chain_row else "stale",
            "warning": None if chain_row else f"{chain_name} chain TVL unavailable",
            "confidence": "medium" if chain_row else "low",
        }
    except Exception as exc:
        logger.info("LP adapter fallback: %s", exc)
        return _static_protocol_fallback(protocols, "lp", normalized_network)


def basis_adapter(protocols: List[str], network: str) -> Dict[str, Any]:
    try:
        return _resolve_protocols(protocols, "basis", network)
    except Exception:
        return _static_protocol_fallback(protocols, "basis", network)


def curated_adapter(protocols: List[str], network: str) -> Dict[str, Any]:
    try:
        stats = _resolve_protocols(protocols, "curated", network)
        if stats.get("tvl") is None:
            stats["risk_flags"].append("Curated vault live TVL unavailable.")
        return stats
    except Exception:
        return _static_protocol_fallback(protocols, "curated", network)


def enrich_live_data(category: str, protocols: List[str], network: str = _DEFAULT_NETWORK) -> Dict[str, Any]:
    normalized_network = _normalize_network(network)
    cache_key = _build_cache_key(category, protocols, normalized_network)
    micro = _micro_get(cache_key)
    if isinstance(micro, dict):
        _metric_inc(_METRIC_CACHE_HITS)
        return dict(micro)

    category_key = (category or "").lower().strip()
    if category_key == "rwa":
        return _with_stale_fallback(cache_key, lambda: rwa_adapter(protocols, normalized_network), category_key, protocols, normalized_network)
    if category_key == "lending" or category_key == "staking":
        return _with_stale_fallback(cache_key, lambda: lending_adapter(protocols, normalized_network), category_key, protocols, normalized_network)
    if category_key == "lp":
        return _with_stale_fallback(cache_key, lambda: lp_adapter(protocols, normalized_network), category_key, protocols, normalized_network)
    if category_key == "basis":
        return _with_stale_fallback(cache_key, lambda: basis_adapter(protocols, normalized_network), category_key, protocols, normalized_network)
    if category_key == "curated" or category_key == "structured":
        return _with_stale_fallback(cache_key, lambda: curated_adapter(protocols, normalized_network), category_key, protocols, normalized_network)
    _metric_inc(_METRIC_FALLBACKS, source="unknown")
    return _fallback("unknown", f"No adapter for category '{category_key}'")
