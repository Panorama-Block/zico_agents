from src.agents.swap.config import SwapConfig


def test_network_alias_resolution():
    assert SwapConfig.validate_network("ETH") == "ethereum"
    assert "avalanche" in SwapConfig.list_networks()


def test_token_policy_lookup():
    canonical = SwapConfig.validate_or_raise("usdc", "avalanche")
    assert canonical == "USDC"
    policy = SwapConfig.get_token_policy("avalanche", canonical)
    assert policy
    assert "decimals" in policy
    assert "min_amount" in policy
