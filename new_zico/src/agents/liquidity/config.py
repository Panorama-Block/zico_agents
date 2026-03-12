"""Configuration for the Liquidity Agent (Aerodrome on Base)."""
from typing import Dict, List, Optional


class LiquidityConfig:
    """Static configuration for Aerodrome LP + Farming on Base."""

    NETWORK = "base"
    CHAIN_ID = 8453
    PROTOCOL = "aerodrome"

    SUPPORTED_ACTIONS = [
        "enter",
        "exit",
        "claim",
    ]

    LEGACY_ACTION_ALIASES = {
        "add_liquidity": "enter",
        "stake": "enter",
        "remove_liquidity": "exit",
        "unstake": "exit",
        "claim_rewards": "claim",
        "claim_reward": "claim",
        "add": "enter",
        "remove": "exit",
    }

    CANONICAL_TO_LEGACY = {
        "enter": "add_liquidity",
        "exit": "remove_liquidity",
        "claim": "claim_rewards",
    }

    # Key token addresses on Base
    WETH = "0x4200000000000000000000000000000000000006"
    USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    USDbC = "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA"
    AERO = "0x940181a94A35A4569E4529A3CDfB74e38FD98631"

    TOKENS: Dict[str, Dict] = {
        "WETH": {"symbol": "WETH", "address": WETH, "decimals": 18},
        "ETH": {"symbol": "ETH", "address": "0x0000000000000000000000000000000000000000", "decimals": 18},
        "USDC": {"symbol": "USDC", "address": USDC, "decimals": 6},
        "USDbC": {"symbol": "USDbC", "address": USDbC, "decimals": 6},
        "AERO": {"symbol": "AERO", "address": AERO, "decimals": 18},
    }

    # Pre-defined pools (pool_id -> config)
    POOLS: Dict[str, Dict] = {
        "weth-usdc-volatile": {
            "token_a": "WETH",
            "token_b": "USDC",
            "stable": False,
            "display": "WETH-USDC-VOLATILE",
            "description": "WETH/USDC volatile pool",
        },
        "weth-aero-volatile": {
            "token_a": "WETH",
            "token_b": "AERO",
            "stable": False,
            "display": "WETH-AERO",
            "description": "WETH/AERO volatile pool",
        },
        "usdc-usdbc-stable": {
            "token_a": "USDC",
            "token_b": "USDbC",
            "stable": True,
            "display": "USDC-USDBC-STABLE",
            "description": "USDC/USDbC stable pool",
        },
        "weth-usdc-stable": {
            "token_a": "WETH",
            "token_b": "USDC",
            "stable": True,
            "display": "WETH-USDC-STABLE",
            "description": "WETH/USDC stable pool",
        },
    }

    POOL_ALIASES: Dict[str, str] = {
        "WETH-USDC": "weth-usdc-volatile",
        "WETH/USDC": "weth-usdc-volatile",
        "WETH-USDC-VOL": "weth-usdc-volatile",
        "WETH-USDC-VOLATILE": "weth-usdc-volatile",
        "WETH-AERO": "weth-aero-volatile",
        "WETH/AERO": "weth-aero-volatile",
        "WETH-AERO-VOLATILE": "weth-aero-volatile",
        "USDC-USDBC": "usdc-usdbc-stable",
        "USDC/USDBC": "usdc-usdbc-stable",
        "USDC-USDBC-STABLE": "usdc-usdbc-stable",
        "WETH-USDC-STABLE": "weth-usdc-stable",
    }

    MIN_AMOUNT = "0.0001"
    DEFAULT_SLIPPAGE_BPS = 50  # 0.5%

    @classmethod
    def get_network(cls) -> str:
        return cls.NETWORK

    @classmethod
    def get_chain_id(cls) -> int:
        return cls.CHAIN_ID

    @classmethod
    def get_protocol(cls) -> str:
        return cls.PROTOCOL

    @classmethod
    def list_actions(cls) -> List[str]:
        return cls.SUPPORTED_ACTIONS

    @classmethod
    def validate_action(cls, action: str) -> str:
        act = action.lower().strip().replace(" ", "_")
        act = cls.LEGACY_ACTION_ALIASES.get(act, act)
        if act not in cls.SUPPORTED_ACTIONS:
            raise ValueError(f"Action '{action}' is not supported. Supported: {cls.SUPPORTED_ACTIONS}")
        return act

    @classmethod
    def to_legacy_action(cls, action: str) -> str:
        return cls.CANONICAL_TO_LEGACY.get(action, action)

    @classmethod
    def get_pool(cls, pool_id: str) -> Optional[Dict]:
        return cls.POOLS.get(pool_id)

    @classmethod
    def list_pools(cls) -> List[str]:
        return list(cls.POOLS.keys())

    @classmethod
    def validate_pool(cls, pool_id: str) -> str:
        pid_raw = pool_id.strip()
        pid = pid_raw.lower()
        pid_alias = pid_raw.upper()
        pid = cls.POOL_ALIASES.get(pid_alias, pid)
        if pid not in cls.POOLS:
            raise ValueError(f"Pool '{pool_id}' not found. Available: {cls.list_pools()}")
        return pid

    @classmethod
    def get_token_decimals(cls, token: str) -> int:
        token_info = cls.TOKENS.get(token.upper()) or cls.TOKENS.get(token)
        if token_info:
            return token_info.get("decimals", 18)
        return 18

    @classmethod
    def get_min_amount(cls) -> str:
        return cls.MIN_AMOUNT

    @classmethod
    def action_needs_pool(cls, action: str) -> bool:
        return action in ("enter", "exit", "claim")

    @classmethod
    def action_needs_amount(cls, action: str) -> bool:
        return action in ("enter", "exit")
