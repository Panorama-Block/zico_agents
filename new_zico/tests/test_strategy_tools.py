import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import httpx  # noqa: F401
    import jwt  # noqa: F401
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(f"Missing runtime dependency: {exc}")

from src.agents.strategy.storage import StrategyStateRepository
from src.agents.strategy.tools import (
    fetch_strategy_candidates_tool,
    update_strategy_intent_tool,
    simulate_strategy_outcomes_tool,
    prepare_strategy_handoff_tool,
    compare_protocol_live_data_tool,
)


class StrategyToolsTest(unittest.TestCase):
    def setUp(self):
        StrategyStateRepository.reset()

    def test_fetch_filters_high_risk_without_opt_in(self):
        result = fetch_strategy_candidates_tool.invoke(
            {
                "user_id": "u1",
                "conversation_id": "c1",
                "risk_tier": "medium",
                "top_k": 3,
                "high_risk_opt_in": False,
            }
        )
        self.assertIn("suggestions", result)
        for item in result["suggestions"]:
            self.assertNotIn(item["risk_profile"], {"high", "very_high"})

    def test_fetch_base_network_registry(self):
        result = fetch_strategy_candidates_tool.invoke(
            {
                "user_id": "ub1",
                "conversation_id": "cb1",
                "risk_tier": "low",
                "network": "base",
                "top_k": 2,
                "high_risk_opt_in": False,
            }
        )
        self.assertEqual(result.get("network"), "base")
        self.assertTrue(result.get("suggestions"))
        for item in result["suggestions"]:
            self.assertTrue(str(item.get("strategy_id", "")).startswith("base_"))

    def test_ready_after_handoff(self):
        fetch_strategy_candidates_tool.invoke(
            {
                "user_id": "u2",
                "conversation_id": "c2",
                "risk_tier": "low",
                "high_risk_opt_in": False,
            }
        )
        update_strategy_intent_tool.invoke(
            {
                "user_id": "u2",
                "conversation_id": "c2",
                "recommended_allocations": [{"strategy_id": "avax_rwa_opentrade_low_v1", "weight": 1.0}],
            }
        )
        simulate_strategy_outcomes_tool.invoke(
            {
                "user_id": "u2",
                "conversation_id": "c2",
            }
        )
        handoff = prepare_strategy_handoff_tool.invoke(
            {
                "user_id": "u2",
                "conversation_id": "c2",
                "strategy_id": "avax_rwa_opentrade_low_v1",
            }
        )
        self.assertEqual(handoff["event"], "strategy_intent_ready")
        self.assertEqual(handoff["status"], "ready")
        self.assertIn("handoff", handoff)

    def test_simulation_uses_live_apy_when_available(self):
        fetch_strategy_candidates_tool.invoke(
            {
                "user_id": "u3",
                "conversation_id": "c3",
                "risk_tier": "low",
                "high_risk_opt_in": False,
            }
        )
        with patch(
            "src.agents.strategy.tools.enrich_live_data",
            return_value={"apy": 0.2, "freshness": "fresh", "source": "defillama", "warning": None},
        ):
            result = simulate_strategy_outcomes_tool.invoke(
                {
                    "user_id": "u3",
                    "conversation_id": "c3",
                }
            )
        by_strategy = result.get("simulation", {}).get("by_strategy", {})
        self.assertTrue(by_strategy)
        first = next(iter(by_strategy.values()))
        self.assertEqual(first["assumptions"]["base_apy"], 0.2)

    def test_simulation_falls_back_to_strategy_base_apy(self):
        fetch_strategy_candidates_tool.invoke(
            {
                "user_id": "u4",
                "conversation_id": "c4",
                "risk_tier": "low",
                "high_risk_opt_in": False,
            }
        )
        with patch(
            "src.agents.strategy.tools.enrich_live_data",
            return_value={"apy": None, "freshness": "stale", "source": "static_assumption", "warning": "no live"},
        ):
            result = simulate_strategy_outcomes_tool.invoke(
                {
                    "user_id": "u4",
                    "conversation_id": "c4",
                }
            )
        by_strategy = result.get("simulation", {}).get("by_strategy", {})
        self.assertTrue(by_strategy)
        first = next(iter(by_strategy.values()))
        self.assertGreater(first["assumptions"]["base_apy"], 0)
        self.assertEqual(result.get("simulation", {}).get("freshness"), "stale")

    def test_compare_protocol_live_data(self):
        with patch(
            "src.agents.strategy.tools.enrich_live_data",
            side_effect=[
                {"apy": 0.07, "source": "defillama", "freshness": "fresh", "as_of": "2026-03-07T00:00:00Z", "confidence": "high", "warning": None},
                {"apy": 0.05, "source": "defillama", "freshness": "fresh", "as_of": "2026-03-07T00:00:00Z", "confidence": "high", "warning": None},
                {"apy": 0.06, "source": "defillama", "freshness": "fresh", "as_of": "2026-03-07T00:00:00Z", "confidence": "high", "warning": None},
            ],
        ):
            result = compare_protocol_live_data_tool.invoke(
                {
                    "user_id": "u5",
                    "conversation_id": "c5",
                    "protocols": ["Hypha", "Euler V2", "Spark"],
                }
            )
        self.assertEqual(result.get("event"), "strategy_protocol_comparison_ready")
        self.assertEqual(result.get("best_protocol"), "Hypha")
        self.assertEqual(len(result.get("comparison", [])), 3)


if __name__ == "__main__":
    unittest.main()
