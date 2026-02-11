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

    # Per-asset amount policies: {network: {symbol: {min_amount, max_amount, decimals}}}
    ASSET_POLICIES: Dict[str, Dict[str, Dict[str, Any]]] = {
        "ethereum": {
            "ETH":  {"min_amount": "0.0001", "max_amount": "10000", "decimals": 18},
            "WETH": {"min_amount": "0.0001", "max_amount": "10000", "decimals": 18},
            "USDC": {"min_amount": "1",      "max_amount": "1000000", "decimals": 6},
            "USDT": {"min_amount": "1",      "max_amount": "1000000", "decimals": 6},
            "DAI":  {"min_amount": "1",      "max_amount": "1000000", "decimals": 18},
            "WBTC": {"min_amount": "0.0001", "max_amount": "100", "decimals": 8},
            "AAVE": {"min_amount": "0.01",   "max_amount": "250000", "decimals": 18},
            "LINK": {"min_amount": "0.01",   "max_amount": "500000", "decimals": 18},
        },
        "arbitrum": {
            "USDC": {"min_amount": "1",      "max_amount": "1000000", "decimals": 6},
            "USDT": {"min_amount": "1",      "max_amount": "1000000", "decimals": 6},
            "DAI":  {"min_amount": "1",      "max_amount": "1000000", "decimals": 18},
            "WBTC": {"min_amount": "0.0001", "max_amount": "100", "decimals": 8},
            "WETH": {"min_amount": "0.0001", "max_amount": "10000", "decimals": 18},
            "ARB":  {"min_amount": "0.1",    "max_amount": "1000000", "decimals": 18},
        },
        "optimism": {
            "USDC": {"min_amount": "1",      "max_amount": "1000000", "decimals": 6},
            "USDT": {"min_amount": "1",      "max_amount": "1000000", "decimals": 6},
            "DAI":  {"min_amount": "1",      "max_amount": "1000000", "decimals": 18},
            "WBTC": {"min_amount": "0.0001", "max_amount": "100", "decimals": 8},
            "WETH": {"min_amount": "0.0001", "max_amount": "10000", "decimals": 18},
            "OP":   {"min_amount": "0.1",    "max_amount": "1000000", "decimals": 18},
        },
        "base": {
            "USDC": {"min_amount": "1",      "max_amount": "1000000", "decimals": 6},
            "WETH": {"min_amount": "0.0001", "max_amount": "10000", "decimals": 18},
            "CBETH": {"min_amount": "0.0001", "max_amount": "10000", "decimals": 18},
        },
        "polygon": {
            "USDC":  {"min_amount": "1",      "max_amount": "1000000", "decimals": 6},
            "USDT":  {"min_amount": "1",      "max_amount": "1000000", "decimals": 6},
            "DAI":   {"min_amount": "1",      "max_amount": "1000000", "decimals": 18},
            "WBTC":  {"min_amount": "0.0001", "max_amount": "100", "decimals": 8},
            "WETH":  {"min_amount": "0.0001", "max_amount": "10000", "decimals": 18},
            "MATIC": {"min_amount": "0.1",    "max_amount": "5000000", "decimals": 18},
        },
        "avalanche": {
            "USDC": {"min_amount": "1",      "max_amount": "1000000", "decimals": 6},
            "USDT": {"min_amount": "1",      "max_amount": "1000000", "decimals": 6},
            "DAI":  {"min_amount": "1",      "max_amount": "1000000", "decimals": 18},
            "WBTC": {"min_amount": "0.0001", "max_amount": "100", "decimals": 8},
            "WETH": {"min_amount": "0.0001", "max_amount": "10000", "decimals": 18},
            "AVAX": {"min_amount": "0.0001", "max_amount": "100000", "decimals": 18},
        },
    }

    # Fallback policy when a specific asset/network pair is not defined.
    DEFAULT_ASSET_POLICY: Dict[str, Any] = {"min_amount": "0.0001", "max_amount": "10000000", "decimals": 18}

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

    @classmethod
    def get_asset_policy(cls, network: str, asset: str) -> Dict[str, Any]:
        """Return the amount policy (min, max, decimals) for a network/asset pair."""
        net = network.lower().strip()
        sym = asset.upper().strip()
        net_policies = cls.ASSET_POLICIES.get(net, {})
        return dict(net_policies.get(sym, cls.DEFAULT_ASSET_POLICY))
