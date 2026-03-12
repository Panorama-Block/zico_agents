import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.agents.liquidity.config import LiquidityConfig
from src.agents.routing.pre_extractor import pre_extract


class LiquidityNormalizationTest(unittest.TestCase):
    def test_validate_action_maps_legacy_to_canonical(self):
        self.assertEqual(LiquidityConfig.validate_action("add_liquidity"), "enter")
        self.assertEqual(LiquidityConfig.validate_action("stake"), "enter")
        self.assertEqual(LiquidityConfig.validate_action("remove_liquidity"), "exit")
        self.assertEqual(LiquidityConfig.validate_action("unstake"), "exit")
        self.assertEqual(LiquidityConfig.validate_action("claim_rewards"), "claim")

    def test_validate_pool_alias_to_canonical(self):
        self.assertEqual(LiquidityConfig.validate_pool("WETH-USDC"), "weth-usdc-volatile")
        self.assertEqual(LiquidityConfig.validate_pool("weth-usdc-volatile"), "weth-usdc-volatile")
        self.assertEqual(LiquidityConfig.validate_pool("USDC-USDBC-STABLE"), "usdc-usdbc-stable")

    def test_pre_extractor_maps_liquidity_actions_to_canonical(self):
        parsed = pre_extract("stake my LP tokens on WETH-USDC", "liquidity")
        self.assertEqual(parsed.action, "enter")

        parsed = pre_extract("remove liquidity from WETH-USDC", "liquidity")
        self.assertEqual(parsed.action, "exit")

        parsed = pre_extract("claim rewards from WETH-USDC", "liquidity")
        self.assertEqual(parsed.action, "claim")

if __name__ == "__main__":
    unittest.main()
