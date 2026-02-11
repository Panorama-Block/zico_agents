"""
Tiered LLM model configuration.

All agents use gemini-2.5-flash. Audio transcription uses gemini-2.0-flash.
"""

from __future__ import annotations


class ModelTier:
    """Canonical model identifiers per tier."""

    FAST = "gemini-2.5-flash"
    EXECUTION = "gemini-2.5-flash"
    TRANSCRIPTION = "gemini-2.0-flash"
    FORMATTER = "gemini-2.0-flash"


# Maps agent runtime names to their optimal tier.
AGENT_TIER_MAP: dict[str, str] = {
    "router":         ModelTier.FAST,
    "default_agent":  ModelTier.FAST,
    "search_agent":   ModelTier.FAST,
    "crypto_agent":   ModelTier.FAST,
    "swap_agent":     ModelTier.FAST,
    "lending_agent":  ModelTier.FAST,
    "staking_agent":  ModelTier.FAST,
    "dca_agent":      ModelTier.FAST,
    "database_agent": ModelTier.FAST,
    "formatter":      ModelTier.FAST,
    "llm_router":     ModelTier.FAST,
}


def model_for_agent(agent_name: str) -> str:
    """Return the recommended model for *agent_name*, defaulting to FAST."""
    return AGENT_TIER_MAP.get(agent_name, ModelTier.FAST)
