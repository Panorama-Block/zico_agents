"""Output discipline tests for cards #67 and #68.

These tests assert that the user-facing surfaces of the liquidity, swap, strategy and routing
agents do not leak provider/protocol names. The strict contract is documented in
`new_zico/docs/agent-capability-contract.md` §3.

Internal data files (`strategy/live_data.py`, `strategy/config.py` scoring constants,
`strategy_registry.*.json`) intentionally reference protocol names — they are NOT
covered here.
"""

from __future__ import annotations

import os
import re
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Banned tokens come from the SPRINT_RIZZI.md #67/#68 audit grep.
BANNED_PROTOCOL_NAMES = ("uniswap", "aerodrome", "traderjoe", "trader joe", "moonwell", "benqi")


def _assert_no_banned_names(self: unittest.TestCase, text: str, where: str) -> None:
    lowered = text.lower()
    for needle in BANNED_PROTOCOL_NAMES:
        self.assertNotIn(
            needle,
            lowered,
            f"{where}: banned protocol name '{needle}' leaked into user-facing text",
        )


class LiquidityOutputContractTest(unittest.TestCase):
    """Card #67 — liquidity agent must not surface providers in user-facing text."""

    def test_liquidity_prompt_has_no_protocol_names(self) -> None:
        from src.agents.liquidity.prompt import LIQUIDITY_AGENT_SYSTEM_PROMPT

        _assert_no_banned_names(self, LIQUIDITY_AGENT_SYSTEM_PROMPT, "liquidity prompt")

    def test_liquidity_module_docstring_has_no_protocol_names(self) -> None:
        import src.agents.liquidity as pkg
        import src.agents.liquidity.agent as agent_mod

        _assert_no_banned_names(self, pkg.__doc__ or "", "liquidity __init__ docstring")
        _assert_no_banned_names(
            self, agent_mod.LiquidityAgent.__doc__ or "", "LiquidityAgent docstring"
        )

    def test_get_liquidity_info_tool_output_has_no_protocol_field(self) -> None:
        try:
            import httpx  # noqa: F401
        except ModuleNotFoundError as exc:
            self.skipTest(f"runtime dep missing: {exc}")

        from src.agents.liquidity.tools import get_liquidity_info_tool

        result = get_liquidity_info_tool.invoke({})
        self.assertNotIn(
            "protocol",
            result,
            "get_liquidity_info must not return a `protocol` field — replaced by `capability`",
        )
        self.assertEqual(result.get("capability"), "liquidity")
        _assert_no_banned_names(self, str(result.get("info", "")), "get_liquidity_info info string")


class SwapOutputContractTest(unittest.TestCase):
    """Card #67 — swap agent stays clean (sanity check, no rewrite expected)."""

    def test_swap_prompt_has_no_protocol_names(self) -> None:
        from src.agents.swap.prompt import SWAP_AGENT_SYSTEM_PROMPT

        _assert_no_banned_names(self, SWAP_AGENT_SYSTEM_PROMPT, "swap prompt")


class StrategyOutputContractTest(unittest.TestCase):
    """Card #68 — strategy recommendations and handoffs must not surface providers.

    Comparison-by-protocol features (e.g. `compare_protocol_live_data`) are out of scope —
    those legitimately echo protocol names back when the user explicitly requested it.
    """

    def setUp(self) -> None:
        try:
            import httpx  # noqa: F401
            import jwt  # noqa: F401
        except ModuleNotFoundError as exc:
            self.skipTest(f"runtime dep missing: {exc}")
        from src.agents.strategy.storage import StrategyStateRepository

        StrategyStateRepository.reset()

    def test_strategy_prompt_has_capability_discipline(self) -> None:
        from src.agents.strategy.prompt import STRATEGY_AGENT_SYSTEM_PROMPT

        self.assertIn(
            "capability",
            STRATEGY_AGENT_SYSTEM_PROMPT.lower(),
            "strategy prompt must instruct the agent to speak capability vocabulary",
        )
        self.assertIn(
            "provider",
            STRATEGY_AGENT_SYSTEM_PROMPT.lower(),
            "strategy prompt must explicitly forbid `provider` in recommendation output",
        )

    def test_candidate_output_has_capability_not_protocols(self) -> None:
        from src.agents.strategy.tools import fetch_strategy_candidates_tool

        result = fetch_strategy_candidates_tool.invoke(
            {
                "user_id": "contract_u1",
                "conversation_id": "contract_c1",
                "risk_tier": "low",
                "top_k": 3,
                "high_risk_opt_in": False,
            }
        )
        suggestions = result.get("suggestions", [])
        self.assertTrue(suggestions, "fetch should return suggestions for low risk tier")
        for item in suggestions:
            self.assertNotIn(
                "protocols",
                item,
                f"strategy candidate {item.get('strategy_id')} must not surface `protocols`",
            )
            self.assertIn(
                "capability",
                item,
                f"strategy candidate {item.get('strategy_id')} must carry a `capability` field",
            )

    def test_handoff_prefilled_has_capability_not_protocols(self) -> None:
        from src.agents.strategy.tools import (
            fetch_strategy_candidates_tool,
            prepare_strategy_handoff_tool,
            simulate_strategy_outcomes_tool,
            update_strategy_intent_tool,
        )

        fetch_strategy_candidates_tool.invoke(
            {
                "user_id": "contract_u2",
                "conversation_id": "contract_c2",
                "risk_tier": "low",
                "high_risk_opt_in": False,
            }
        )
        update_strategy_intent_tool.invoke(
            {
                "user_id": "contract_u2",
                "conversation_id": "contract_c2",
                "recommended_allocations": [
                    {"strategy_id": "avax_rwa_opentrade_low_v1", "weight": 1.0}
                ],
            }
        )
        simulate_strategy_outcomes_tool.invoke(
            {"user_id": "contract_u2", "conversation_id": "contract_c2"}
        )
        handoff = prepare_strategy_handoff_tool.invoke(
            {
                "user_id": "contract_u2",
                "conversation_id": "contract_c2",
                "strategy_id": "avax_rwa_opentrade_low_v1",
            }
        )
        prefilled = (handoff.get("metadata") or {}).get("handoff", {}).get("prefilled_fields", {})
        self.assertNotIn(
            "protocols",
            prefilled,
            "handoff prefilled must not include `protocols` — replaced by `capability`",
        )
        self.assertIn(
            "capability",
            prefilled,
            "handoff prefilled must carry a `capability` slug for the downstream agent",
        )


class SemanticRouterExemplarsTest(unittest.TestCase):
    """Card #68 — routing exemplars must not contain banned protocol names."""

    def test_routing_exemplars_audit_clean(self) -> None:
        from src.agents.routing.semantic_router import INTENT_EXEMPLARS

        # Allow names that double as token tickers (e.g. AERO) — narrow audit to the DoD grep list.
        pattern = re.compile(r"\b(uniswap|aerodrome|trader\s?joe|moonwell|benqi|lido)\b", re.IGNORECASE)
        offenders: list[tuple[str, str]] = []
        for category, phrases in INTENT_EXEMPLARS.items():
            for phrase in phrases:
                if pattern.search(phrase):
                    offenders.append((category.value, phrase))
        self.assertEqual(
            offenders,
            [],
            f"semantic router exemplars must not name protocols. Offenders: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
