from decimal import Decimal
from importlib import reload

import pytest


@pytest.fixture
def dca_tools(monkeypatch):
    import src.agents.dca.storage as storage

    storage.DcaStateRepository.reset()
    storage = reload(storage)
    storage.DcaStateRepository.reset()

    import src.agents.dca.tools as tools

    tools = reload(tools)
    try:
        yield tools
    finally:
        storage.DcaStateRepository.reset()


def test_fetch_strategy_suggestions(dca_tools):
    tools = dca_tools
    with tools.dca_session("user-test", "conversation-test"):
        result = tools.fetch_dca_strategy_tool(from_token="USDC", to_token="AVAX", cadence="daily")
        assert result["event"] == "dca_strategy_suggestions"
        assert isinstance(result["suggestions"], list)
        assert result["suggestions"], "expected at least one strategy suggestion"


def test_update_dca_flow(dca_tools):
    tools = dca_tools
    with tools.dca_session("user-flow", "conversation-flow"):
        step1 = tools.update_dca_intent_tool(
            strategy_id="swap_dca_daily_v1",
            strategy_version="2024-06-01",
            strategy_name="Daily Stablecoin to Bluechip DCA",
            strategy_summary="Mock summary",
            from_token="USDC",
            to_token="AVAX",
        )
        assert step1["stage"] == "recommendation"
        assert step1["next_action"]["field"] == "cadence"

        step2 = tools.update_dca_intent_tool(
            cadence="daily",
            start_on="2024-06-10",
            iterations=10,
            total_amount=Decimal("1000"),
            venue="pangolin",
            slippage_bps=40,
        )
        assert step2["stage"] == "confirmation"
        assert step2["next_action"]["field"] == "confirmation"

        final = tools.update_dca_intent_tool(confirm=True)
        assert final["event"] == "dca_intent_ready"
        assert final["metadata"]["workflow_type"] == "dca_swap"
        assert final["metadata"]["tokens"]["from"] == "USDC"
        assert final["metadata"]["tokens"]["to"] == "AVAX"
