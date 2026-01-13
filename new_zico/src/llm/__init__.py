"""
LLM Module - Multi-provider LLM abstraction layer.

This module provides:
- LLMFactory: Create LLM instances for multiple providers (Google, OpenAI, Anthropic)
- CostTrackingCallback: Track token usage and costs per LLM call
"""

from .factory import LLMFactory, detect_provider, MODEL_PROVIDERS
from .cost_tracker import CostTrackingCallback
from .exceptions import (
    LLMError,
    LLMProviderError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMInvalidModelError,
)

__all__ = [
    # Factory
    "LLMFactory",
    "detect_provider",
    "MODEL_PROVIDERS",
    # Cost tracking
    "CostTrackingCallback",
    # Exceptions
    "LLMError",
    "LLMProviderError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMInvalidModelError",
]
