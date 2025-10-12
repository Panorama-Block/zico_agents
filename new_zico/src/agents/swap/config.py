"""Network-aware swap configuration helpers loaded from a registry file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set, Tuple


class SwapConfig:
    """Expose swap metadata so tools can validate user input safely."""

    _REGISTRY_PATH: Path = Path(__file__).with_name("registry.json")
    _NETWORK_TOKENS: Dict[str, Set[str]] = {}
    _NETWORK_ALIASES: Dict[str, str] = {}
    _TOKEN_ALIASES: Dict[str, str] = {}
    _TOKEN_DETAILS: Dict[str, Dict[str, Dict[str, Any]]] = {}
    _SUPPORTED_ROUTES: Set[Tuple[str, str]] = set()
    _GLOBAL_TOKENS: Set[str] = set()
    _LOADED: bool = False

    # ---------- Registry management ----------
    @classmethod
    def reload(cls) -> None:
        data = cls._load_registry()
        cls._rebuild(data)

    @classmethod
    def _ensure_loaded(cls) -> None:
        if not cls._LOADED:
            cls.reload()

    @classmethod
    def _load_registry(cls) -> Dict[str, Any]:
        try:
            raw = cls._REGISTRY_PATH.read_text()
        except FileNotFoundError as exc:
            raise RuntimeError(f"Swap registry not found: {cls._REGISTRY_PATH}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON registry for swap config: {exc}") from exc
        if not isinstance(data, dict):
            raise RuntimeError("Swap registry must be a JSON object with 'networks'.")
        return data

    @classmethod
    def _rebuild(cls, data: Dict[str, Any]) -> None:
        network_tokens: Dict[str, Set[str]] = {}
        network_aliases: Dict[str, str] = {}
        token_aliases: Dict[str, str] = {}
        token_details: Dict[str, Dict[str, Dict[str, Any]]] = {}
        global_tokens: Set[str] = set()

        for network in data.get("networks", []):
            if not isinstance(network, dict):
                continue
            name = (network.get("name") or "").strip().lower()
            if not name:
                continue
            aliases = [name, *(network.get("aliases") or [])]
            for alias in aliases:
                alias_key = (alias or "").strip().lower()
                if alias_key:
                    network_aliases[alias_key] = name

            tokens_for_network: Set[str] = set()
            details_for_network: Dict[str, Dict[str, Any]] = {}
            for token in network.get("tokens", []):
                if not isinstance(token, dict):
                    continue
                symbol = (token.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                tokens_for_network.add(symbol)
                clean = dict(token)
                clean["symbol"] = symbol
                details_for_network[symbol] = clean
                global_tokens.add(symbol)
                token_aliases[symbol.lower()] = symbol
                for alias in token.get("aliases", []):
                    alias_key = (alias or "").strip().lower()
                    if alias_key:
                        token_aliases[alias_key] = symbol

            network_tokens[name] = tokens_for_network
            token_details[name] = details_for_network

        routes = data.get("routes", "all")
        supported_routes: Set[Tuple[str, str]]
        if routes == "all":
            supported_routes = {
                (src, dst) for src in network_tokens for dst in network_tokens
            }
        else:
            supported_routes = set()
            for route in routes or []:
                if isinstance(route, dict):
                    src = (route.get("from") or "").strip().lower()
                    dst = (route.get("to") or "").strip().lower()
                elif isinstance(route, (list, tuple)) and len(route) == 2:
                    src = (route[0] or "").strip().lower()
                    dst = (route[1] or "").strip().lower()
                else:
                    continue
                src_key = network_aliases.get(src)
                dst_key = network_aliases.get(dst)
                if src_key and dst_key:
                    supported_routes.add((src_key, dst_key))

        cls._NETWORK_TOKENS = network_tokens
        cls._NETWORK_ALIASES = network_aliases
        cls._TOKEN_ALIASES = token_aliases
        cls._TOKEN_DETAILS = token_details
        cls._GLOBAL_TOKENS = global_tokens
        cls._SUPPORTED_ROUTES = supported_routes
        cls._LOADED = True

    # ---------- Public helpers ----------
    @classmethod
    def list_networks(cls) -> Iterable[str]:
        """Return supported networks in a stable order."""
        cls._ensure_loaded()
        return sorted(cls._NETWORK_TOKENS.keys())

    @classmethod
    def list_tokens(cls, network: str) -> Iterable[str]:
        """Return supported tokens for a given network."""
        cls._ensure_loaded()
        normalized = cls._normalize_network(network)
        tokens = cls._NETWORK_TOKENS.get(normalized)
        if tokens is None:
            raise ValueError(
                f"Unsupported network '{network}'. Available: {sorted(cls._NETWORK_TOKENS)}"
            )
        return sorted(tokens)

    @classmethod
    def validate_network(cls, network: str) -> str:
        """Return the canonical network name or raise ValueError."""
        return cls._normalize_network(network)

    @classmethod
    def validate_or_raise(cls, token: str, network: Optional[str] = None) -> str:
        """Validate a token, optionally scoping by network, and return canonical symbol."""
        cls._ensure_loaded()
        canonical = cls._normalize_token(token)
        if network is not None:
            normalized_network = cls._normalize_network(network)
            tokens = cls._NETWORK_TOKENS.get(normalized_network, set())
            if canonical not in tokens:
                raise ValueError(
                    f"Unsupported token '{token}' on {normalized_network}. Available: {sorted(tokens)}"
                )
        elif canonical not in cls._GLOBAL_TOKENS:
            raise ValueError(
                f"Unsupported token '{token}'. Supported tokens: {sorted(cls._GLOBAL_TOKENS)}"
            )
        return canonical

    @classmethod
    def routes_supported(cls, from_network: str, to_network: str) -> bool:
        """Return whether a swap route is supported."""
        cls._ensure_loaded()
        source = cls._normalize_network(from_network)
        dest = cls._normalize_network(to_network)
        return (source, dest) in cls._SUPPORTED_ROUTES

    @classmethod
    def list_supported(cls) -> Iterable[str]:
        """Return all supported tokens across networks."""
        cls._ensure_loaded()
        return sorted(cls._GLOBAL_TOKENS)

    @classmethod
    def get_token_policy(cls, network: str, token: str) -> Dict[str, Any]:
        """Return token metadata (decimals, min/max amounts) for a network/token pair."""
        cls._ensure_loaded()
        normalized_network = cls._normalize_network(network)
        canonical = cls._normalize_token(token)
        policy = cls._TOKEN_DETAILS.get(normalized_network, {}).get(canonical, {})
        return dict(policy)

    # ---------- Internal helpers ----------
    @classmethod
    def _normalize_network(cls, network: str) -> str:
        cls._ensure_loaded()
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
        cls._ensure_loaded()
        key = (token or "").strip().lower()
        if not key:
            raise ValueError("Token is required.")
        return cls._TOKEN_ALIASES.get(key, key.upper())


# Ensure the registry is warm on import so validation errors surface early.
SwapConfig._ensure_loaded()
