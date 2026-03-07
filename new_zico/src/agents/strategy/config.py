"""Configuration and constants for the strategy agent."""

from __future__ import annotations

import os
from typing import Final


class StrategyConfig:
    FEATURE_FLAG_ENABLED: Final[bool] = os.getenv("STRATEGY_AGENT_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    SUPPORTED_NETWORKS: Final[set[str]] = {"avalanche", "base"}
    DEFAULT_NETWORK: Final[str] = os.getenv("STRATEGY_DEFAULT_NETWORK", "avalanche").strip().lower() or "avalanche"

    WORKFLOW_TYPE: Final[str] = "yield_strategy"
    DEFAULT_TOP_K: Final[int] = 3
    MAX_TOP_K: Final[int] = 5
    DEFAULT_HORIZONS_DAYS: Final[list[int]] = [30, 90, 180]

    RISK_TIERS: Final[set[str]] = {"low", "medium", "high"}
    STRATEGY_RISK_LEVELS: Final[set[str]] = {"low", "medium", "high", "very_high"}
    STAGES: Final[tuple[str, ...]] = (
        "profiling",
        "discovery",
        "recommendation",
        "comparison",
        "confirmation",
        "ready",
    )

    CATEGORY_STRESS_SCENARIOS: Final[dict[str, str]] = {
        "rwa": "credit_default",
        "lending": "liquidation_risk",
        "lp": "impermanent_loss",
        "staking": "validator_slash_or_depeg",
        "basis": "funding_flip",
        "structured": "volatility_shock",
        "curated": "manager_underperformance",
    }

    ALLOWED_PROTOCOLS: Final[set[str]] = {
        "OpenTrade",
        "Securitize",
        "Centrifuge Protocol",
        "Euler V2",
        "MEV Capital",
        "Re7 Labs",
        "Varlamore Capital",
        "Hypha",
        "Spark",
        "XSY",
        "LFJ",
        "Blackhole",
        "Pharaoh Exchange",
        "K3 Capital",
        "Avant Protocol",
        "Morpho Blue",
        "Ondo Finance",
        "Aerodrome",
        "Beefy Finance",
        "Yearn",
        "Rocket Pool",
        "Uniswap V3",
        "Perpetual Markets",
        "Ethena",
    }

    PROTOCOL_RISK_PENALTY: Final[dict[str, float]] = {
        "Euler V2": 0.08,
        "LFJ": 0.10,
        "Blackhole": 0.12,
        "Pharaoh Exchange": 0.12,
        "XSY": 0.14,
        "Centrifuge Protocol": 0.10,
        "MEV Capital": 0.09,
        "Re7 Labs": 0.07,
        "Varlamore Capital": 0.08,
        "Avant Protocol": 0.15,
        "OpenTrade": 0.05,
        "Securitize": 0.06,
        "Hypha": 0.06,
        "Spark": 0.07,
        "K3 Capital": 0.11,
        "Morpho Blue": 0.08,
        "Ondo Finance": 0.06,
        "Aerodrome": 0.11,
        "Beefy Finance": 0.09,
        "Yearn": 0.08,
        "Rocket Pool": 0.07,
        "Uniswap V3": 0.12,
        "Perpetual Markets": 0.16,
        "Ethena": 0.15,
    }

    LIVE_DATA_TTL_SEC: Final[int] = int(os.getenv("STRATEGY_LIVE_DATA_TTL_SEC", "120"))
    LIVE_DATA_STALE_TTL_SEC: Final[int] = int(os.getenv("STRATEGY_LIVE_DATA_STALE_TTL_SEC", "600"))
    LIVE_DATA_ERROR_TTL_SEC: Final[int] = int(os.getenv("STRATEGY_LIVE_DATA_ERROR_TTL_SEC", "30"))


def normalize_risk_tier(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.lower().strip()
    if normalized in StrategyConfig.RISK_TIERS:
        return normalized
    return None


def normalize_strategy_network(value: str | None) -> str:
    normalized = (value or StrategyConfig.DEFAULT_NETWORK).strip().lower()
    if normalized in StrategyConfig.SUPPORTED_NETWORKS:
        return normalized
    return StrategyConfig.DEFAULT_NETWORK
