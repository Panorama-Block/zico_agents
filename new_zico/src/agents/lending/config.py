"""Configuration for the Lending Agent."""
from typing import List, Dict, Any

class LendingConfig:
    """Static configuration for supported lending assets and networks."""

    # TODO: Fetch this from the Lending Service API dynamically if possible.
    SUPPORTED_NETWORKS = ["ethereum", "arbitrum", "optimism", "base", "polygon", "avalanche"]
    
    SUPPORTED_ASSETS = {
        "ethereum": ["ETH", "USDC", "USDT", "DAI", "WBTC", "WETH", "AAVE", "LINK"],
        "arbitrum": ["USDC", "USDT", "DAI", "WBTC", "WETH", "ARB"],
        "optimism": ["USDC", "USDT", "DAI", "WBTC", "WETH", "OP"],
        "base": ["USDC", "WETH", "CBETH"],
        "polygon": ["USDC", "USDT", "DAI", "WBTC", "WETH", "MATIC"],
        "avalanche": ["USDC", "USDT", "DAI", "WBTC", "WETH", "AVAX"],
    }

    SUPPORTED_ACTIONS = ["supply", "borrow", "repay", "withdraw"]

    @classmethod
    def list_networks(cls) -> List[str]:
        return cls.SUPPORTED_NETWORKS

    @classmethod
    def list_assets(cls, network: str) -> List[str]:
        return cls.SUPPORTED_ASSETS.get(network.lower(), [])

    @classmethod
    def validate_network(cls, network: str) -> str:
        net = network.lower().strip()
        if net not in cls.SUPPORTED_NETWORKS:
            raise ValueError(f"Network '{network}' is not supported. Supported: {cls.SUPPORTED_NETWORKS}")
        return net

    @classmethod
    def validate_asset(cls, asset: str, network: str) -> str:
        net = cls.validate_network(network)
        symbol = asset.upper().strip()
        supported = cls.list_assets(net)
        if symbol not in supported:
            raise ValueError(f"Asset '{asset}' is not supported on {net}. Supported: {supported}")
        return symbol

    @classmethod
    def validate_action(cls, action: str) -> str:
        act = action.lower().strip()
        if act not in cls.SUPPORTED_ACTIONS:
            raise ValueError(f"Action '{action}' is not supported. Supported: {cls.SUPPORTED_ACTIONS}")
        return act
