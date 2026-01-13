"""
Custom exceptions for LLM module.
"""


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    def __init__(self, message: str, provider: str | None = None, model: str | None = None):
        self.provider = provider
        self.model = model
        super().__init__(message)


class LLMProviderError(LLMError):
    """Raised when there's an error with the LLM provider."""

    pass


class LLMTimeoutError(LLMError):
    """Raised when an LLM request times out."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        model: str | None = None,
        retry_after: int | None = None,
    ):
        self.retry_after = retry_after
        super().__init__(message, provider, model)


class LLMInvalidModelError(LLMError):
    """Raised when an invalid model is specified."""

    def __init__(self, model: str, available_models: list[str] | None = None):
        self.available_models = available_models or []
        message = f"Invalid model: {model}"
        if available_models:
            message += f". Available models: {', '.join(available_models)}"
        super().__init__(message, model=model)
