import os
import sys
import time
import json
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.agents.strategy import live_data


class _FakeCache:
    def __init__(self):
        self.store = {}
        self.exp = {}

    def _alive(self, key: str) -> bool:
        exp = self.exp.get(key)
        if exp is None:
            return key in self.store
        if time.time() > exp:
            self.store.pop(key, None)
            self.exp.pop(key, None)
            return False
        return True

    def get_json(self, key: str):
        return self.store.get(key) if self._alive(key) else None

    def set_json(self, key: str, value, ttl: int):
        self.store[key] = value
        self.exp[key] = time.time() + ttl

    def set_error(self, key: str, payload, ttl: int):
        self.set_json(key, {"__error__": True, "payload": payload}, ttl=ttl)

    def incr(self, key: str, ttl: int):
        value = int(self.store.get(key, 0) or 0) + 1
        self.store[key] = value
        self.exp[key] = time.time() + ttl
        return value

    def exists(self, key: str):
        return self._alive(key)


class LiveDataTest(unittest.TestCase):
    def setUp(self):
        self.cache = _FakeCache()
        live_data._CACHE = self.cache
        live_data._MICRO_CACHE.clear()

    def test_slug_mapping_known_protocol(self):
        self.assertEqual(live_data._defillama_protocol_slug("Euler V2"), "euler-v2")

    def test_alias_matching_variants(self):
        self.assertTrue(live_data._project_matches_protocol("spark-savings", "Spark"))
        self.assertTrue(live_data._project_matches_protocol("joe-v2.1", "LFJ"))
        self.assertTrue(live_data._project_matches_protocol("blackhole-clmm", "Blackhole"))

    def test_fresh_cache_hit(self):
        key = live_data._build_cache_key("lending", ["Spark"])
        self.cache.set_json(
            key,
            {"payload": {"apy": 0.09, "freshness": "fresh", "source": "defillama"}, "_cached_at": time.time()},
            ttl=live_data._STALE_TTL,
        )
        with patch("src.agents.strategy.live_data.lending_adapter", side_effect=RuntimeError("should not fetch")):
            result = live_data.enrich_live_data("lending", ["Spark"])
        self.assertEqual(result["apy"], 0.09)
        self.assertEqual(result["freshness"], "fresh")

    def test_stale_cache_used_on_fetch_failure(self):
        key = live_data._build_cache_key("lending", ["Spark"])
        self.cache.set_json(
            key,
            {"payload": {"apy": 0.08, "freshness": "fresh", "source": "defillama"}, "_cached_at": time.time() - 240},
            ttl=live_data._STALE_TTL,
        )
        with patch("src.agents.strategy.live_data.lending_adapter", side_effect=RuntimeError("network")):
            result = live_data.enrich_live_data("lending", ["Spark"])
        self.assertEqual(result["apy"], 0.08)
        self.assertEqual(result["freshness"], "stale")

    def test_negative_cache_triggers_static_fallback(self):
        key = live_data._build_cache_key("lending", ["Spark"])
        self.cache.set_error(f"{key}:error", {"err": "timeout"}, ttl=live_data._ERROR_TTL)
        result = live_data.enrich_live_data("lending", ["Spark"])
        self.assertEqual(result["source"], "static_assumption")
        self.assertEqual(result["confidence"], "low")
        self.assertIsNotNone(result.get("apy"))

    def test_source_failover_to_static_when_no_pool_and_no_protocol_stats(self):
        with patch("src.agents.strategy.live_data._fetch_pool_apy", return_value=None), patch(
            "src.agents.strategy.live_data._fetch_protocol_stats", side_effect=RuntimeError("boom")
        ):
            result = live_data.enrich_live_data("lending", ["Spark"])
        self.assertEqual(result["source"], "static_assumption")
        self.assertEqual(result["confidence"], "low")

    def test_protocol_adapter_map_covers_all_registry_protocols(self):
        registry_protocols = set()
        for registry_name in ("strategy_registry.avalanche.json", "strategy_registry.base.json"):
            registry = json.loads(
                Path(
                    f"/home/inteli/Área de trabalho/projects/panorama/zico_agent/new_zico/src/agents/strategy/{registry_name}"
                ).read_text(encoding="utf-8")
            )
            registry_protocols.update({p for s in registry for p in s.get("protocols", [])})
        adapter_protocols = set(live_data._PROTOCOL_ADAPTERS.keys())
        self.assertTrue(registry_protocols.issubset(adapter_protocols))

    def test_multi_protocol_strategy_selects_best_apy(self):
        with patch(
            "src.agents.strategy.live_data._PROTOCOL_ADAPTERS",
            {
                "Hypha": lambda _network: {
                    "apy": 0.07,
                    "tvl": 1000.0,
                    "capacity": "ok",
                    "risk_flags": [],
                    "as_of": "now",
                    "source": "defillama",
                    "freshness": "fresh",
                    "warning": None,
                    "confidence": "high",
                },
                "Euler V2": lambda _network: {
                    "apy": 0.05,
                    "tvl": 2000.0,
                    "capacity": "ok",
                    "risk_flags": [],
                    "as_of": "now",
                    "source": "defillama",
                    "freshness": "fresh",
                    "warning": None,
                    "confidence": "high",
                },
            },
        ):
            result = live_data.enrich_live_data("structured", ["Hypha", "Euler V2"])
        self.assertEqual(result["protocol"], "Hypha")
        self.assertEqual(result["apy"], 0.07)


if __name__ == "__main__":
    unittest.main()
