"""Configuration for the Staking Agent (Lido on Ethereum)."""
from typing import List


class StakingConfig:
    """Static configuration for Lido staking on Ethereum Mainnet."""

    # Fixed network - Lido staking is only on Ethereum Mainnet
    NETWORK = "ethereum"
    CHAIN_ID = 1
    PROTOCOL = "lido"

    # Supported actions
    SUPPORTED_ACTIONS = ["stake", "unstake"]

    # Token addresses on Ethereum Mainnet
    ETH_ADDRESS = "0x0000000000000000000000000000000000000000"
    STETH_ADDRESS = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"
    WSTETH_ADDRESS = "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0"

    # Token configuration
    TOKENS = {
        "ETH": {
            "symbol": "ETH",
            "address": ETH_ADDRESS,
            "decimals": 18,
        },
        "stETH": {
            "symbol": "stETH",
            "address": STETH_ADDRESS,
            "decimals": 18,
        },
        "wstETH": {
            "symbol": "wstETH",
            "address": WSTETH_ADDRESS,
            "decimals": 18,
        },
    }

    # Minimum amounts (in ETH)
    MIN_STAKE_AMOUNT = "0.0001"
    MIN_UNSTAKE_AMOUNT = "0.0001"

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
        act = action.lower().strip()
        if act not in cls.SUPPORTED_ACTIONS:
            raise ValueError(f"Action '{action}' is not supported. Supported: {cls.SUPPORTED_ACTIONS}")
        return act

    @classmethod
    def get_input_token(cls, action: str) -> str:
        """Get the input token based on action."""
        if action == "stake":
            return "ETH"
        return "stETH"

    @classmethod
    def get_output_token(cls, action: str) -> str:
        """Get the output token based on action."""
        if action == "stake":
            return "stETH"
        return "ETH"

    @classmethod
    def get_token_decimals(cls, token: str) -> int:
        token_info = cls.TOKENS.get(token.upper()) or cls.TOKENS.get(token)
        if token_info:
            return token_info.get("decimals", 18)
        return 18

    @classmethod
    def get_min_amount(cls, action: str) -> str:
        if action == "stake":
            return cls.MIN_STAKE_AMOUNT
        return cls.MIN_UNSTAKE_AMOUNT
