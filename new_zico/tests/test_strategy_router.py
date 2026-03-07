import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import numpy  # noqa: F401
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(f"Missing runtime dependency: {exc}")

from src.agents.routing.semantic_router import IntentCategory, _INTENT_AGENT_MAP, INTENT_EXEMPLARS


class StrategyRouterTest(unittest.TestCase):
    def test_strategy_intent_registered(self):
        self.assertIn(IntentCategory.STRATEGY, INTENT_EXEMPLARS)
        self.assertEqual(_INTENT_AGENT_MAP[IntentCategory.STRATEGY], "strategy_agent")


if __name__ == "__main__":
    unittest.main()
