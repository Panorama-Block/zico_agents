"""
Configuration for the Portfolio Advisor agent.

Uses free, keyless APIs:
  • Blockscout  — ETH, Polygon, Arbitrum, Base, Optimism
  • Routescan   — Avalanche
"""

# ---------------------------------------------------------------------------
# Blockscout instances (no API key required)
# ---------------------------------------------------------------------------
BLOCKSCOUT_CHAINS: dict[str, str] = {
    "ethereum": "https://eth.blockscout.com",
    "polygon": "https://polygon.blockscout.com",
    "arbitrum": "https://arbitrum.blockscout.com",
    "base": "https://base.blockscout.com",
    "optimism": "https://optimism.blockscout.com",
}

# ---------------------------------------------------------------------------
# Routescan (no API key required) — chain name → EVM chain ID
# ---------------------------------------------------------------------------
ROUTESCAN_CHAINS: dict[str, int] = {
    "avalanche": 43114,
}

# ---------------------------------------------------------------------------
# Native token metadata per chain
# ---------------------------------------------------------------------------
NATIVE_SYMBOL: dict[str, str] = {
    "ethereum": "ETH",
    "polygon": "POL",
    "arbitrum": "ETH",
    "base": "ETH",
    "optimism": "ETH",
    "avalanche": "AVAX",
}

NATIVE_DECIMALS: int = 18

# ---------------------------------------------------------------------------
# Classification sets
# ---------------------------------------------------------------------------
STABLECOIN_SYMBOLS: set[str] = {
    "USDC", "USDT", "DAI", "TUSD", "BUSD", "FRAX", "MIM", "USDe",
}

BLUE_CHIP_SYMBOLS: set[str] = {
    "ETH", "WETH", "BTC", "WBTC", "BNB", "AVAX", "WAVAX", "MATIC", "POL",
}

# Minimum USD value for a position to be included in the report.
MIN_VALUE_USD: float = 0.01
