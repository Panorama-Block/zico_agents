from decimal import Decimal
from importlib import reload

import pytest


@pytest.fixture
def swap_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("SWAP_STATE_PATH", str(tmp_path / "swap_state.json"))

    import src.agents.swap.storage as storage
    storage.SwapStateRepository.reset()
    storage = reload(storage)
    storage.SwapStateRepository.reset()

    import src.agents.swap.tools as tools
    tools = reload(tools)
    try:
        yield tools
    finally:
        storage.SwapStateRepository.reset()


def test_update_swap_flow(swap_tools):
    tools = swap_tools

    with tools.swap_session("user-test", "conversation-test"):
        step1 = tools.update_swap_intent_tool(from_token="AVAX")
        assert step1["next_action"]["field"] == "from_network"

        step2 = tools.update_swap_intent_tool(from_network="avalanche")
        assert step2["next_action"]["field"] == "to_network"

        step3 = tools.update_swap_intent_tool(to_network="ethereum")
        assert step3["next_action"]["field"] == "to_token"

        step4 = tools.update_swap_intent_tool(to_token="USDC")
        assert step4["next_action"]["field"] == "amount"

        final = tools.update_swap_intent_tool(amount=Decimal("10"))
        assert final["event"] == "swap_intent_ready"
        assert final["metadata"]["amount"] == "10"
        assert final["metadata"]["status"] == "ready"
        assert final["metadata"]["history"]
