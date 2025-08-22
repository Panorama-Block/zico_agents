class SwapConfig:
    """Configuration and simple interface for supported swap tokens.

    This provides a canonical set of allowed token symbols and helpers to
    normalize and validate user input before executing swaps.
    """

    # Canonical symbols for Avalanche swaps (expand as needed)
    SUPPORTED_TOKENS = {
        "AVAX",   # Native token
        "WAVAX",  # Wrapped AVAX
        "USDC",
        "USDT",
        "DAI",
        "WBTC",
        "WETH",
    }

    @classmethod
    def normalize_symbol(cls, symbol: str) -> str:
        """Return canonical uppercase symbol without surrounding whitespace."""
        return (symbol or "").strip().upper()

    @classmethod
    def is_supported(cls, symbol: str) -> bool:
        """Check if a token symbol is supported (case-insensitive)."""
        return cls.normalize_symbol(symbol) in cls.SUPPORTED_TOKENS

    @classmethod
    def validate_or_raise(cls, symbol: str) -> str:
        """Validate token symbol and return its canonical form, or raise ValueError."""
        canonical = cls.normalize_symbol(symbol)
        if canonical not in cls.SUPPORTED_TOKENS:
            raise ValueError(
                f"Unsupported token '{symbol}'. Supported tokens: {sorted(cls.SUPPORTED_TOKENS)}"
            )
        return canonical

    @classmethod
    def list_supported(cls):
        """Return a sorted list of supported token symbols."""
        return sorted(cls.SUPPORTED_TOKENS)    