"""
Portfolio tools — fetches multi-chain wallet balances via free, keyless APIs.

Data sources:
  • Blockscout API v2 — ETH, Polygon, Arbitrum, Base, Optimism
  • Routescan API v2  — Avalanche

Both APIs return token balances with USD pricing included, so no separate
price-feed is needed.

Session management follows the same ContextVar pattern used by the swap,
lending, and staking agents so the wallet_address is injected by the graph
node rather than asked from the user.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from typing import Any, Dict, List, Optional

import requests
from langchain_core.tools import tool
from pydantic import BaseModel

from src.agents.portfolio.config import (
    BLOCKSCOUT_CHAINS,
    BLUE_CHIP_SYMBOLS,
    MIN_VALUE_USD,
    NATIVE_DECIMALS,
    NATIVE_SYMBOL,
    ROUTESCAN_CHAINS,
    STABLECOIN_SYMBOLS,
)

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 15  # seconds per request

# ---------------------------------------------------------------------------
# Session context (user_id, conversation_id, wallet_address)
# ---------------------------------------------------------------------------

_CURRENT_SESSION: ContextVar[tuple[str, str, str]] = ContextVar(
    "_current_portfolio_session",
    default=("", "", ""),
)


def set_current_portfolio_session(
    user_id: Optional[str],
    conversation_id: Optional[str],
    wallet_address: Optional[str],
) -> None:
    _CURRENT_SESSION.set((
        (user_id or "").strip(),
        (conversation_id or "").strip(),
        (wallet_address or "").strip(),
    ))


def clear_current_portfolio_session() -> None:
    _CURRENT_SESSION.set(("", "", ""))


@contextmanager
def portfolio_session(
    user_id: Optional[str],
    conversation_id: Optional[str],
    wallet_address: Optional[str],
):
    """Context manager that guarantees session scoping for portfolio tool calls."""
    set_current_portfolio_session(user_id, conversation_id, wallet_address)
    try:
        yield
    finally:
        clear_current_portfolio_session()


# ---------------------------------------------------------------------------
# Simple TTL cache (avoids hammering explorers on follow-up questions)
# ---------------------------------------------------------------------------

_PORTFOLIO_CACHE: Dict[str, tuple[Any, float]] = {}
_CACHE_TTL = 60  # seconds
_cache_lock = Lock()


def _get_cached(key: str) -> Optional[Any]:
    with _cache_lock:
        entry = _PORTFOLIO_CACHE.get(key)
        if entry and (time.time() - entry[1]) < _CACHE_TTL:
            return entry[0]
        return None


def _set_cached(key: str, value: Any) -> None:
    with _cache_lock:
        _PORTFOLIO_CACHE[key] = (value, time.time())


# ---------------------------------------------------------------------------
# Blockscout helpers
# ---------------------------------------------------------------------------

def _blockscout_fetch_address(base_url: str, address: str) -> Dict[str, Any]:
    """GET /api/v2/addresses/{addr} — native balance + coin exchange rate."""
    try:
        resp = requests.get(
            f"{base_url}/api/v2/addresses/{address}",
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Blockscout address fetch failed (%s): %s", base_url, exc)
        return {}


def _blockscout_fetch_tokens(base_url: str, address: str) -> List[Dict[str, Any]]:
    """GET /api/v2/addresses/{addr}/token-balances — ERC-20 holdings with price."""
    try:
        resp = requests.get(
            f"{base_url}/api/v2/addresses/{address}/token-balances",
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()  # list of token objects
    except Exception as exc:
        logger.warning("Blockscout token-balances fetch failed (%s): %s", base_url, exc)
        return []


def _process_blockscout_chain(
    chain_name: str,
    base_url: str,
    address: str,
) -> List[Dict[str, Any]]:
    """Fetch and normalise all holdings on a single Blockscout-indexed chain."""
    assets: List[Dict[str, Any]] = []

    # ── Native token ──
    addr_data = _blockscout_fetch_address(base_url, address)
    if addr_data:
        try:
            raw_balance = int(addr_data.get("coin_balance") or "0")
            balance = raw_balance / (10 ** NATIVE_DECIMALS)
            exchange_rate = float(addr_data.get("exchange_rate") or 0)
            value_usd = balance * exchange_rate
            symbol = NATIVE_SYMBOL.get(chain_name, "ETH")
            if value_usd >= MIN_VALUE_USD or balance >= 0.000001:
                assets.append({
                    "symbol": symbol,
                    "name": symbol,
                    "balance": round(balance, 6),
                    "value_usd": round(value_usd, 2),
                    "chain": chain_name,
                    "contract_address": "native",
                    "category": _classify(symbol),
                })
        except (ValueError, TypeError):
            pass

    # ── ERC-20 tokens ──
    tokens = _blockscout_fetch_tokens(base_url, address)
    for tok in tokens:
        try:
            token_info = tok.get("token", {})
            decimals = int(token_info.get("decimals") or 18)
            raw_value = int(tok.get("value") or "0")
            balance = raw_value / (10 ** decimals)
            if balance <= 0:
                continue

            symbol = (token_info.get("symbol") or "???").upper()
            exchange_rate = float(token_info.get("exchange_rate") or 0)
            value_usd = balance * exchange_rate

            if value_usd < MIN_VALUE_USD and balance < 0.000001:
                continue

            assets.append({
                "symbol": symbol,
                "name": token_info.get("name", symbol),
                "balance": round(balance, 6),
                "value_usd": round(value_usd, 2),
                "chain": chain_name,
                "contract_address": token_info.get("address_hash", ""),
                "category": _classify(symbol),
            })
        except (ValueError, TypeError):
            continue

    return assets


# ---------------------------------------------------------------------------
# Routescan helpers
# ---------------------------------------------------------------------------

_ROUTESCAN_BASE = "https://api.routescan.io/v2/network/mainnet/evm"


def _routescan_fetch_tokens(chain_id: int, address: str) -> List[Dict[str, Any]]:
    """GET /v2/network/mainnet/evm/{chainId}/address/{addr}/erc20-holdings."""
    try:
        resp = requests.get(
            f"{_ROUTESCAN_BASE}/{chain_id}/address/{address}/erc20-holdings",
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])
    except Exception as exc:
        logger.warning("Routescan fetch failed (chain %s): %s", chain_id, exc)
        return []


def _routescan_fetch_native(chain_id: int, address: str) -> Dict[str, Any]:
    """GET /v2/network/mainnet/evm/{chainId}/address/{addr}."""
    try:
        resp = requests.get(
            f"{_ROUTESCAN_BASE}/{chain_id}/address/{address}",
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Routescan native fetch failed (chain %s): %s", chain_id, exc)
        return {}


def _process_routescan_chain(
    chain_name: str,
    chain_id: int,
    address: str,
) -> List[Dict[str, Any]]:
    """Fetch and normalise all holdings on a single Routescan-indexed chain."""
    assets: List[Dict[str, Any]] = []

    # ── Native token ──
    native_data = _routescan_fetch_native(chain_id, address)
    if native_data:
        try:
            raw_balance = int(native_data.get("balance") or "0")
            balance = raw_balance / (10 ** NATIVE_DECIMALS)
            # Routescan native endpoint may not include price;
            # use CoinGecko-style fallback only for AVAX
            native_price = float(native_data.get("tokenPriceUsd") or 0)
            value_usd = balance * native_price
            symbol = NATIVE_SYMBOL.get(chain_name, "AVAX")
            if value_usd >= MIN_VALUE_USD or balance >= 0.000001:
                assets.append({
                    "symbol": symbol,
                    "name": symbol,
                    "balance": round(balance, 6),
                    "value_usd": round(value_usd, 2),
                    "chain": chain_name,
                    "contract_address": "native",
                    "category": _classify(symbol),
                })
        except (ValueError, TypeError):
            pass

    # ── ERC-20 tokens ──
    tokens = _routescan_fetch_tokens(chain_id, address)
    for tok in tokens:
        try:
            decimals = int(tok.get("tokenDecimals") or 18)
            raw_qty = int(tok.get("tokenQuantity") or "0")
            balance = raw_qty / (10 ** decimals)
            if balance <= 0:
                continue

            symbol = (tok.get("tokenSymbol") or "???").upper()
            value_usd = float(tok.get("tokenValueInUsd") or 0)

            if value_usd < MIN_VALUE_USD and balance < 0.000001:
                continue

            assets.append({
                "symbol": symbol,
                "name": tok.get("tokenName", symbol),
                "balance": round(balance, 6),
                "value_usd": round(value_usd, 2),
                "chain": chain_name,
                "contract_address": tok.get("tokenAddress", ""),
                "category": _classify(symbol),
            })
        except (ValueError, TypeError):
            continue

    return assets


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify(symbol: str) -> str:
    upper = symbol.upper()
    if upper in STABLECOIN_SYMBOLS:
        return "stablecoin"
    if upper in BLUE_CHIP_SYMBOLS:
        return "blue_chip"
    return "altcoin"


# ---------------------------------------------------------------------------
# The Tool
# ---------------------------------------------------------------------------

class _GetPortfolioArgs(BaseModel):
    """No user-facing args — wallet_address comes from the session context."""
    pass


@tool("get_user_portfolio", args_schema=_GetPortfolioArgs)
def get_user_portfolio_tool() -> str:
    """Fetch the connected user's multi-chain token holdings with USD values.

    Returns a JSON object with total_value_usd, top_holdings, allocation
    breakdown (stablecoins %, blue_chips %, altcoins %), and the full
    asset list.  Use this data to analyze portfolio risk and concentration.
    """
    _, _, wallet_address = _CURRENT_SESSION.get()

    if not wallet_address:
        return json.dumps({"error": "No wallet address available. Ask the user to connect their wallet."})

    # Check cache
    cache_key = f"portfolio:{wallet_address.lower()}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # ── Fetch all chains in parallel ──
    all_assets: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {}

        # Blockscout chains
        for chain_name, base_url in BLOCKSCOUT_CHAINS.items():
            fut = pool.submit(_process_blockscout_chain, chain_name, base_url, wallet_address)
            futures[fut] = chain_name

        # Routescan chains
        for chain_name, chain_id in ROUTESCAN_CHAINS.items():
            fut = pool.submit(_process_routescan_chain, chain_name, chain_id, wallet_address)
            futures[fut] = chain_name

        for fut in as_completed(futures):
            chain = futures[fut]
            try:
                all_assets.extend(fut.result())
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", chain, exc)

    if not all_assets:
        return json.dumps({
            "wallet_address": wallet_address,
            "total_value_usd": 0,
            "asset_count": 0,
            "chains_checked": list(BLOCKSCOUT_CHAINS.keys()) + list(ROUTESCAN_CHAINS.keys()),
            "top_holdings": [],
            "allocation": {"stablecoins_pct": 0, "blue_chips_pct": 0, "altcoins_pct": 0},
            "all_assets": [],
            "note": "No token balances found. The wallet may be empty or the APIs may be temporarily unavailable.",
        })

    # ── Aggregate ──
    total_value = sum(a["value_usd"] for a in all_assets)
    for a in all_assets:
        a["percentage"] = round((a["value_usd"] / total_value * 100) if total_value > 0 else 0, 2)

    all_assets.sort(key=lambda a: a["value_usd"], reverse=True)

    stablecoins_usd = sum(a["value_usd"] for a in all_assets if a["category"] == "stablecoin")
    blue_chips_usd = sum(a["value_usd"] for a in all_assets if a["category"] == "blue_chip")
    altcoins_usd = sum(a["value_usd"] for a in all_assets if a["category"] == "altcoin")

    result = json.dumps({
        "wallet_address": wallet_address,
        "total_value_usd": round(total_value, 2),
        "asset_count": len(all_assets),
        "chains_checked": list(BLOCKSCOUT_CHAINS.keys()) + list(ROUTESCAN_CHAINS.keys()),
        "top_holdings": all_assets[:5],
        "allocation": {
            "stablecoins_pct": round((stablecoins_usd / total_value * 100) if total_value > 0 else 0, 1),
            "blue_chips_pct": round((blue_chips_usd / total_value * 100) if total_value > 0 else 0, 1),
            "altcoins_pct": round((altcoins_usd / total_value * 100) if total_value > 0 else 0, 1),
        },
        "all_assets": all_assets,
    })

    _set_cached(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_tools() -> list:
    """Return the toolset for the portfolio advisor agent."""
    return [get_user_portfolio_tool]
