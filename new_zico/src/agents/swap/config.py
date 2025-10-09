"""Network-aware swap configuration helpers."""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Set, Tuple


class SwapConfig:
    """Expose swap metadata so tools can validate user input safely."""

    # Canonical networks we support. Values are the tokens available on that chain.
    _NETWORK_TOKENS: Dict[str, Set[str]] = {
        "avalanche": {
            "AVAX",
            "WAVAX",
            "UNI",
            "USDC",
            "USDT",
            "AAVE",
            "BTC.B",
            "JOE",
            "MIM",
        },
        "ethereum": {
            "ETH",
            "WETH",
            "USDC",
            "USDT",
            "WBTC",
            "AAVE",
            "UNI",
            "LINK",
            "LDO",
            "USDE",
            "DAI",
        },
        "binance-smart-chain": {
            "USDT",
            "USDC",
            "CAKE",
            "ADA",
            "DOGE",
            "XRP",
            "DOT",
            "TUSD",
        },
        "polygon": {
            "USDT",
            "USDC",
            "WETH",
            "DAI",
            "QUICK",
            "AAVE",
            "SAND",
        },
        "arbitrum": {
            "ARB",
            "USDT",
            "USDC",
            "ETH",
            "GMX",
        },
        "base": {
            "USDC",
            "ETH",
            "CBBTC",
            "AERO",
        },
        "optimism": {
            "USDC",
            "USDT",
            "OP",
        },
    }

    # Friendly aliases -> canonical keys
    _NETWORK_ALIASES: Dict[str, str] = {
        "avax": "avalanche",
        "avalanche": "avalanche",
        "ethereum": "ethereum",
        "eth": "ethereum",
        "ethereum mainnet": "ethereum",
        "binance smart chain": "binance-smart-chain",
        "binance-smart-chain": "binance-smart-chain",
        "bsc": "binance-smart-chain",
        "bnb": "binance-smart-chain",
        "polygon": "polygon",
        "matic": "polygon",
        "arbitrum": "arbitrum",
        "arbitrum one": "arbitrum",
        "base": "base",
        "optimism": "optimism",
    }

    _TOKEN_ALIASES: Dict[str, str] = {
        "avax": "AVAX",
        "wavax": "WAVAX",
        "usdc": "USDC",
        "usdt": "USDT",
        "dai": "DAI",
        "btc.b": "BTC.B",
        "btcb": "BTC.B",
        "wbtc": "WBTC",
        "eth": "ETH",
        "weth": "WETH",
        "uni": "UNI",
        "aave": "AAVE",
        "joe": "JOE",
        "mim": "MIM",
        "link": "LINK",
        "chainlink": "LINK",
        "ldo": "LDO",
        "usde": "USDE",
        "cake": "CAKE",
        "ada": "ADA",
        "doge": "DOGE",
        "xrp": "XRP",
        "dot": "DOT",
        "tusd": "TUSD",
        "quick": "QUICK",
        "sand": "SAND",
        "arb": "ARB",
        "gmx": "GMX",
        "cbbtc": "CBBTC",
        "cb-btc": "CBBTC",
        "aero": "AERO",
        "op": "OP",
    }

    # Optional allow list of directional routes (canonical network names).
    _SUPPORTED_ROUTES: Set[Tuple[str, str]] = set()
    for _src in _NETWORK_TOKENS.keys():
        for _dst in _NETWORK_TOKENS.keys():
            _SUPPORTED_ROUTES.add((_src, _dst))

    # ---------- Public helpers ----------
    @classmethod
    def list_networks(cls) -> Iterable[str]:
        """Return supported networks in a stable order."""
        return sorted(cls._NETWORK_TOKENS.keys())

    @classmethod
    def list_tokens(cls, network: str) -> Iterable[str]:
        """Return supported tokens for a given network."""
        normalized = cls._normalize_network(network)
        if normalized not in cls._NETWORK_TOKENS:
            raise ValueError(
                f"Unsupported network '{network}'. Available: {sorted(cls._NETWORK_TOKENS)}"
            )
        return sorted(cls._NETWORK_TOKENS[normalized])

    @classmethod
    def validate_network(cls, network: str) -> str:
        """Return the canonical network name or raise ValueError."""
        return cls._normalize_network(network)

    @classmethod
    def validate_or_raise(cls, token: str, network: Optional[str] = None) -> str:
        """Validate a token, optionally scoping by network, and return canonical symbol."""
        canonical = cls._normalize_token(token)
        if network is not None:
            normalized_network = cls._normalize_network(network)
            tokens = cls._NETWORK_TOKENS.get(normalized_network, set())
            if canonical not in tokens:
                raise ValueError(
                    f"Unsupported token '{token}' on {normalized_network}. Available: {sorted(tokens)}"
                )
        elif canonical not in cls._all_tokens():
            raise ValueError(
                f"Unsupported token '{token}'. Supported tokens: {sorted(cls._all_tokens())}"
            )
        return canonical

    @classmethod
    def routes_supported(cls, from_network: str, to_network: str) -> bool:
        """Return whether a swap route is supported."""
        source = cls._normalize_network(from_network)
        dest = cls._normalize_network(to_network)
        return (source, dest) in cls._SUPPORTED_ROUTES

    @classmethod
    def list_supported(cls) -> Iterable[str]:
        """Backwards compatible helper returning all tokens across networks."""
        return sorted(cls._all_tokens())

    # ---------- Internal helpers ----------
    @classmethod
    def _normalize_network(cls, network: str) -> str:
        key = (network or "").strip().lower()
        if not key:
            raise ValueError("Network is required.")
        normalized = cls._NETWORK_ALIASES.get(key)
        if normalized is None:
            raise ValueError(
                f"Unsupported network '{network}'. Available: {sorted(cls._NETWORK_TOKENS)}"
            )
        return normalized

    @classmethod
    def _normalize_token(cls, token: str) -> str:
        key = (token or "").strip().lower()
        if not key:
            raise ValueError("Token is required.")
        return cls._TOKEN_ALIASES.get(key, key.upper())

    @classmethod
    def _all_tokens(cls) -> Set[str]:
        tokens: Set[str] = set()
        for chain_tokens in cls._NETWORK_TOKENS.values():
            tokens.update(chain_tokens)
        return tokens
