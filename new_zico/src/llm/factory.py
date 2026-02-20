"""
LLM Factory - Multi-provider LLM abstraction.

Supports:
- Google (Gemini)
- OpenAI (GPT)
- Anthropic (Claude)
"""

import os
from typing import Literal

from langchain_core.language_models import BaseChatModel

from .exceptions import LLMInvalidModelError, LLMProviderError

Provider = Literal["google", "openai", "anthropic"]

MODEL_PROVIDERS: dict[Provider, list[str]] = {
    "google": [
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
    ],
    "anthropic": [
        "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ],
}

# Flatten for quick lookup
ALL_MODELS: set[str] = {model for models in MODEL_PROVIDERS.values() for model in models}


def detect_provider(model: str) -> Provider:
    """
    Detect the provider based on model name.

    Args:
        model: The model name (e.g., 'gemini-2.5-flash', 'gpt-4o')

    Returns:
        The provider name ('google', 'openai', 'anthropic')

    Raises:
        LLMInvalidModelError: If the model is not recognized
    """
    model_lower = model.lower()

    # Check by prefix
    if model_lower.startswith("gemini"):
        return "google"
    if model_lower.startswith("gpt"):
        return "openai"
    if model_lower.startswith("claude"):
        return "anthropic"

    # Check in known models
    for provider, models in MODEL_PROVIDERS.items():
        if model in models:
            return provider

    raise LLMInvalidModelError(model, list(ALL_MODELS))


class LLMFactory:
    """Factory for creating LLM instances across multiple providers."""

    # Cache for LLM instances (singleton per model+config)
    _instances: dict[str, BaseChatModel] = {}

    @classmethod
    def create(
        cls,
        model: str,
        temperature: float = 0.7,
        max_retries: int = 3,
        timeout: int = 60,
        api_key: str | None = None,
        use_cache: bool = True,
        **kwargs,
    ) -> BaseChatModel:
        """
        Create an LLM instance for the specified model.

        Args:
            model: Model name (e.g., 'gemini-2.5-flash', 'gpt-4o', 'claude-sonnet-4-20250514')
            temperature: Sampling temperature (0.0 to 1.0)
            max_retries: Maximum number of retries on failure
            timeout: Request timeout in seconds
            api_key: Optional API key (defaults to environment variable)
            use_cache: Whether to use cached instances
            **kwargs: Additional provider-specific arguments

        Returns:
            BaseChatModel instance

        Raises:
            LLMInvalidModelError: If model is not recognized
            LLMProviderError: If provider initialization fails
        """
        # Check cache
        cache_key = f"{model}:{temperature}:{timeout}"
        if use_cache and cache_key in cls._instances:
            return cls._instances[cache_key]

        provider = detect_provider(model)

        try:
            llm = cls._create_for_provider(
                provider=provider,
                model=model,
                temperature=temperature,
                max_retries=max_retries,
                timeout=timeout,
                api_key=api_key,
                **kwargs,
            )

            if use_cache:
                cls._instances[cache_key] = llm

            return llm

        except ImportError as e:
            raise LLMProviderError(
                f"Provider '{provider}' dependencies not installed: {e}",
                provider=provider,
                model=model,
            )
        except Exception as e:
            raise LLMProviderError(
                f"Failed to create LLM for '{model}': {e}",
                provider=provider,
                model=model,
            )

    @classmethod
    def _create_for_provider(
        cls,
        provider: Provider,
        model: str,
        temperature: float,
        max_retries: int,
        timeout: int,
        api_key: str | None,
        **kwargs,
    ) -> BaseChatModel:
        """Create LLM instance for a specific provider."""
        match provider:
            case "google":
                return cls._create_google(
                    model, temperature, max_retries, timeout, api_key, **kwargs
                )
            case "openai":
                return cls._create_openai(
                    model, temperature, max_retries, timeout, api_key, **kwargs
                )
            case "anthropic":
                return cls._create_anthropic(
                    model, temperature, max_retries, timeout, api_key, **kwargs
                )

    @staticmethod
    def _create_google(
        model: str,
        temperature: float,
        max_retries: int,
        timeout: int,
        api_key: str | None,
        callbacks: list | None = None,
        **kwargs,
    ) -> BaseChatModel:
        """Create Google Gemini LLM instance."""
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout,
            google_api_key=api_key or os.getenv("GEMINI_API_KEY"),
            callbacks=callbacks,
            **kwargs,
        )

    @staticmethod
    def _create_openai(
        model: str,
        temperature: float,
        max_retries: int,
        timeout: int,
        api_key: str | None,
        callbacks: list | None = None,
        **kwargs,
    ) -> BaseChatModel:
        """Create OpenAI LLM instance."""
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            callbacks=callbacks,
            **kwargs,
        )

    @staticmethod
    def _create_anthropic(
        model: str,
        temperature: float,
        max_retries: int,
        timeout: int,
        api_key: str | None,
        callbacks: list | None = None,
        **kwargs,
    ) -> BaseChatModel:
        """Create Anthropic Claude LLM instance."""
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout,
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            callbacks=callbacks,
            **kwargs,
        )

    @classmethod
    def list_models(cls, provider: Provider | None = None) -> list[str]:
        """
        List available models.

        Args:
            provider: Optional provider to filter by

        Returns:
            List of model names
        """
        if provider:
            return MODEL_PROVIDERS.get(provider, [])
        return list(ALL_MODELS)

    @classmethod
    def list_providers(cls) -> list[Provider]:
        """List available providers."""
        return list(MODEL_PROVIDERS.keys())

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the LLM instance cache."""
        cls._instances.clear()

    @classmethod
    def get_default_model(cls, provider: Provider | None = None) -> str:
        """
        Get the default model for a provider.

        Args:
            provider: Provider name (defaults to 'google')

        Returns:
            Default model name
        """
        provider = provider or "google"
        models = MODEL_PROVIDERS.get(provider, [])
        if not models:
            raise LLMProviderError(f"No models available for provider: {provider}")
        return models[0]
