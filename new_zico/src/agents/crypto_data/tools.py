import logging
import json
import httpx
import time
from functools import wraps
from cachetools import TTLCache
from cachetools.keys import hashkey
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.agents.crypto_data.config import Config
from langchain_core.tools import Tool
from src.agents.metadata import metadata

# -----------------------------------------------------------------------------
# Module: crypto_data tools
# -----------------------------------------------------------------------------
# This module provides helper functions and LangChain Tool wrappers to:
#  - Fetch cryptocurrency prices, market data, and fully diluted valuation
#  - Retrieve NFT floor prices
#  - Query DeFi protocol TVL from DefiLlama
#  - Perform fuzzy matching on protocol names
#
# Usage:
#   from src.agents.crypto_data.tools import get_tools
#   tools = get_tools()
#   agent = create_react_agent(model=llm, tools=tools)
# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class CircuitBreakerError(Exception):
    """Raised when the circuit breaker is open."""
    pass

# Caches
# Short TTL for prices (1 minute)
price_cache = TTLCache(maxsize=1000, ttl=60)
# Longer TTL for metadata and lists (1 hour)
metadata_cache = TTLCache(maxsize=1000, ttl=3600)

class SimpleCircuitBreaker:
    """
    A simple circuit breaker implementation.
    If 'failure_threshold' failures occur within 'recovery_timeout' seconds,
    the circuit opens and raises CircuitBreakerError for 'recovery_timeout' seconds.
    """
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.is_open = False

    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if self.is_open:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.is_open = False
                    self.failures = 0
                    logger.info("Circuit breaker recovering...")
                else:
                    logger.warning("Circuit breaker open. Failing fast.")
                    raise CircuitBreakerError("Circuit breaker is open")

            try:
                result = await func(*args, **kwargs)
                # Reset failures on success if we were closed but had some failures
                if self.failures > 0:
                    self.failures = 0
                return result
            except Exception as e:
                self.failures += 1
                self.last_failure_time = time.time()
                if self.failures >= self.failure_threshold:
                    self.is_open = True
                    logger.error(f"Circuit breaker tripped! {self.failures} failures.")
                raise e
        return wrapper

# Global circuit breaker for external APIs
api_circuit_breaker = SimpleCircuitBreaker(failure_threshold=5, recovery_timeout=60)

def async_cached(cache):
    """
    Decorator to cache the result of an async function.
    Uses cachetools.keys.hashkey to generate keys.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = hashkey(*args, **kwargs)
            try:
                return cache[key]
            except KeyError:
                pass
            
            val = await func(*args, **kwargs)
            cache[key] = val
            return val
        return wrapper
    return decorator

@api_circuit_breaker
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True
)
async def _make_request(url: str, params: dict = None) -> dict | None:
    """Helper to make async HTTP requests with error handling."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        return response.json()

def get_most_similar(text: str, data: list[str]) -> list[str]:
    """
    Find the top entries in `data` most semantically similar to `text`.
    Uses TF-IDF vectorization + cosine similarity.

    Args:
        text: The input string to match against.
        data: A list of candidate strings.

    Returns:
        A list of candidates where similarity > 0.5 (up to 20 items).
    """
    if not data:
        return []
    try:
        vectorizer = TfidfVectorizer()
        sentence_vectors = vectorizer.fit_transform(data)
        text_vector = vectorizer.transform([text])

        # Compute cosine similarity between input and all candidates
        similarity_scores = cosine_similarity(text_vector, sentence_vectors)

        # Pick top 20 indices, then filter by threshold
        top_indices = similarity_scores.argsort()[0][-20:]
        top_matches = [data[i] for i in top_indices if similarity_scores[0][i] > 0.5]
        return top_matches
    except Exception as e:
        logger.error(f"Error in fuzzy matching: {e}")
        return []


@async_cached(cache=metadata_cache)
async def get_coingecko_id(text: str, type: str = "coin") -> str | None:
    """
    Look up the CoinGecko internal ID for a coin or NFT by name.

    Args:
        text: Human-readable coin or NFT name or slug.
        type: Either 'coin' or 'nft'.

    Returns:
        The CoinGecko ID string, or None if not found.
    """
    url = f"{Config.COINGECKO_BASE_URL}/search"
    params = {"query": text}
    try:
        data = await _make_request(url, params)
    except Exception as e:
        logger.error(f"Failed to search CoinGecko: {e}")
        return None
    
    if not data:
        return None

    if type == "coin":
        return data["coins"][0]["id"] if data.get("coins") else None
    elif type == "nft":
        return data.get("nfts", [])[0].get("id") if data.get("nfts") else None
    else:
        logger.warning(f"Invalid type specified for get_coingecko_id: {type}")
        return None


@async_cached(cache=metadata_cache)
async def get_tradingview_symbol(coingecko_id: str) -> str | None:
    """
    Convert a CoinGecko coin ID into a TradingView ticker symbol.

    Args:
        coingecko_id: The CoinGecko coin ID.

    Returns:
        A string like 'CRYPTO:BTCUSD', or None if symbol is missing.
    """
    url = f"{Config.COINGECKO_BASE_URL}/coins/{coingecko_id}"
    try:
        data = await _make_request(url)
    except Exception as e:
        logger.error(f"Failed to get TradingView symbol: {e}")
        return None

    if not data:
        return None
        
    symbol = data.get("symbol", "").upper()
    return f"CRYPTO:{symbol}USD" if symbol else None


@async_cached(cache=price_cache)
async def get_price(coin: str) -> float | None:
    """
    Fetch the current USD price of a cryptocurrency.

    Args:
        coin: Human-readable coin name (e.g. 'bitcoin').

    Returns:
        Price in USD as a float, or None if coin not found.
    """
    try:
        coin_id = await get_coingecko_id(coin, type="coin")
        if not coin_id:
            return None

        url = f"{Config.COINGECKO_BASE_URL}/simple/price"
        params = {"ids": coin_id, "vs_currencies": "USD"}
        data = await _make_request(url, params)
        
        if not data or coin_id not in data:
            return None
            
        return data[coin_id].get("usd")
    except Exception as e:
        logger.error(f"Failed to get price for {coin}: {e}")
        return None


@async_cached(cache=price_cache)
async def get_floor_price(nft: str) -> float | None:
    """
    Retrieve the floor price in USD for an NFT collection.

    Args:
        nft: The NFT collection name or slug.

    Returns:
        Floor price in USD, or None if not found.
    """
    try:
        nft_id = await get_coingecko_id(nft, type="nft")
        if not nft_id:
            return None

        url = f"{Config.COINGECKO_BASE_URL}/nfts/{nft_id}"
        data = await _make_request(url)
        
        if not data or "floor_price" not in data:
            return None
            
        return data["floor_price"].get("usd")
    except Exception as e:
        logger.error(f"Failed to get floor price for {nft}: {e}")
        return None


@async_cached(cache=price_cache)
async def get_fdv(coin: str) -> float | None:
    """
    Get a coin's Fully Diluted Valuation (FDV) in USD from CoinGecko.

    Args:
        coin: Coin name or slug.

    Returns:
        FDV in USD, or None if not available.
    """
    try:
        coin_id = await get_coingecko_id(coin, type="coin")
        if not coin_id:
            return None

        url = f"{Config.COINGECKO_BASE_URL}/coins/{coin_id}"
        data = await _make_request(url)
        
        if not data:
            return None
            
        return data.get("market_data", {}).get("fully_diluted_valuation", {}).get("usd")
    except Exception as e:
        logger.error(f"Failed to get FDV for {coin}: {e}")
        return None


@async_cached(cache=price_cache)
async def get_market_cap(coin: str) -> float | None:
    """
    Fetch current market capitalization for a coin via CoinGecko.

    Args:
        coin: The coin name or slug.

    Returns:
        Market cap in USD, or None if not found.
    """
    try:
        coin_id = await get_coingecko_id(coin, type="coin")
        if not coin_id:
            return None

        url = f"{Config.COINGECKO_BASE_URL}/coins/markets"
        params = {"ids": coin_id, "vs_currency": "USD"}
        data = await _make_request(url, params)
        
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
            
        return data[0].get("market_cap")
    except Exception as e:
        logger.error(f"Failed to get market cap for {coin}: {e}")
        return None


@async_cached(cache=metadata_cache)
async def get_protocols_list() -> tuple[list[str], list[str], list[str]]:
    """
    Pull the full list of DeFi protocols from DefiLlama.

    Returns:
        - slugs: List of protocol slugs (for TVL lookup)
        - names: Human-readable names
        - gecko_ids: CoinGecko IDs for integration
    """
    try:
        url = f"{Config.DEFILLAMA_BASE_URL}/protocols"
        data = await _make_request(url)
        
        if not data:
            return [], [], []
            
        slugs = [item["slug"] for item in data]
        names = [item["name"] for item in data]
        gecko_ids = [item.get("gecko_id") for item in data]
        return slugs, names, gecko_ids
    except Exception as e:
        logger.error(f"Failed to get protocols list: {e}")
        return [], [], []


@async_cached(cache=price_cache)
async def get_tvl_value(protocol_id: str) -> float | None:
    """
    Query DefiLlama for a single protocol's TVL.

    Args:
        protocol_id: The slug identifier for the protocol.

    Returns:
        TVL value.
    """
    try:
        # Note: DefiLlama /tvl/{slug} endpoint is better for specific protocol TVL
        url = f"{Config.DEFILLAMA_BASE_URL}/tvl/{protocol_id}"
        data = await _make_request(url)
        
        # The /tvl/{slug} endpoint returns a raw number directly
        if isinstance(data, (int, float)):
            return float(data)
        return None
    except Exception as e:
        logger.error(f"Failed to get TVL for {protocol_id}: {e}")
        return None


async def get_protocol_tvl(protocol_name: str) -> dict[str, float] | None:
    """
    Get a protocol's TVL by name, using fuzzy matching if needed.

    1. Try exact match via CoinGecko ID → DefiLlama slug
    2. If no exact match, find closest names via TF-IDF
    3. Return the highest TVL among matches
    """
    slugs, names, gecko_ids = await get_protocols_list()
    if not slugs:
        return None
        
    tag = await get_coingecko_id(protocol_name)
    protocol_id = None

    if tag:
        # map gecko_id to DefiLlama slug
        # Use next with default None to avoid StopIteration
        protocol_id = next((s for s, g in zip(slugs, gecko_ids) if g == tag), None)
        if protocol_id:
            tvl = await get_tvl_value(protocol_id)
            if tvl is not None:
                return {tag: tvl}

    # fallback: fuzzy text matching on protocol names
    matches = get_most_similar(protocol_name, names)
    if not matches:
        return None

    # fetch TVL for each matched name, pick the highest
    results = []
    for name in matches:
        pid = next((s for s, n in zip(slugs, names) if n == name), None)
        if pid:
            tvl = await get_tvl_value(pid)
            if tvl is not None:
                results.append({pid: tvl})

    if not results:
        return None
        
    return max(results, key=lambda d: next(iter(d.values())))


# -----------------------------------------------------------------------------
# Tool wrappers: these catch errors, format responses, and produce strings
# -----------------------------------------------------------------------------

async def _append_coin_metadata_suffix(text: str, coin_name: str) -> str:
    """
    Append a structured metadata sentinel to a human-friendly text response.
    Includes CoinGecko coinId and uppercased symbol when available.
    """
    try:
        coin_id = await get_coingecko_id(coin_name, type="coin")
        if not coin_id:
            return text
        tv_symbol = await get_tradingview_symbol(coin_id)
        symbol = None
        if tv_symbol and tv_symbol.startswith("CRYPTO:") and tv_symbol.endswith("USD"):
            symbol = tv_symbol[len("CRYPTO:"):-3]
        meta = {"coinId": coin_id}
        if symbol:
            meta["symbol"] = symbol
        response = f"{text} ||META: {json.dumps(meta)}||"
        return response
    except Exception:
        # Never break user-visible responses due to metadata failures
        return text


async def get_coin_price_tool(coin_name: str) -> dict:
    """ 
    LangChain Tool: Return a user-friendly string with the coin's USD price.
    """
    try:
        price = await get_price(coin_name)
        if price is None:
            return Config.PRICE_FAILURE_MESSAGE
        text = Config.PRICE_SUCCESS_MESSAGE.format(coin_name=coin_name, price=price)
        # compute metadata out-of-band
        meta = {}
        try:
            coin_id = await get_coingecko_id(coin_name, type="coin")
            if coin_id:
                tv_symbol = await get_tradingview_symbol(coin_id)
                meta["coinId"] = tv_symbol # return the symbol as the coinId
                metadata.set_crypto_data_agent(meta)
        except Exception:
            pass

        return {"text": text, "metadata": meta}
    except Exception:
        return {"text": Config.API_ERROR_MESSAGE, "metadata": {}}


async def get_nft_floor_price_tool(nft_name: str) -> str:
    """
    LangChain Tool: Return a user-friendly string with the NFT floor price.
    """
    try:
        floor_price = await get_floor_price(nft_name)
        if floor_price is None:
            return Config.FLOOR_PRICE_FAILURE_MESSAGE
        return Config.FLOOR_PRICE_SUCCESS_MESSAGE.format(nft_name=nft_name, floor_price=floor_price)
    except Exception:
        return Config.API_ERROR_MESSAGE


async def get_protocol_total_value_locked_tool(protocol_name: str) -> str:
    """
    LangChain Tool: Return formatted TVL information for a DeFi protocol.
    """
    try:
        tvl = await get_protocol_tvl(protocol_name)
        if tvl is None:
            return Config.TVL_FAILURE_MESSAGE
        tag, tvl_value = next(iter(tvl.items()))
        return Config.TVL_SUCCESS_MESSAGE.format(protocol_name=protocol_name, tvl=tvl_value)
    except Exception:
        return Config.API_ERROR_MESSAGE


async def get_fully_diluted_valuation_tool(coin_name: str) -> str:
    """
    LangChain Tool: Return a formatted string with the coin's FDV.
    """
    try:
        fdv = await get_fdv(coin_name)
        if fdv is None:
            return Config.FDV_FAILURE_MESSAGE
        text = Config.FDV_SUCCESS_MESSAGE.format(coin_name=coin_name, fdv=fdv)
        return await _append_coin_metadata_suffix(text, coin_name)
    except Exception:
        return Config.API_ERROR_MESSAGE


async def get_coin_market_cap_tool(coin_name: str) -> str:
    """
    LangChain Tool: Return a formatted string with the coin's market cap.
    """
    try:
        market_cap = await get_market_cap(coin_name)
        if market_cap is None:
            return Config.MARKET_CAP_FAILURE_MESSAGE
        text = Config.MARKET_CAP_SUCCESS_MESSAGE.format(coin_name=coin_name, market_cap=market_cap)
        return await _append_coin_metadata_suffix(text, coin_name)
    except Exception:
        return Config.API_ERROR_MESSAGE


class _CoinNameArgs(BaseModel):
    coin_name: str = Field(..., description="Name of the cryptocurrency to look up.")


class _NFTNameArgs(BaseModel):
    nft_name: str = Field(..., description="Name or slug of the NFT collection.")


class _ProtocolNameArgs(BaseModel):
    protocol_name: str = Field(..., description="Name of the DeFi protocol.")


def get_tools() -> list[Tool]:
    """
    Build and return the list of LangChain Tools for use in an agent.

    Each Tool wraps one of the user-facing helper functions above.
    """

    return [
        Tool(
            name="get_coin_price",
            func=None,
            coroutine=get_coin_price_tool,
            args_schema=_CoinNameArgs,
            description=(
                "Use this to get the current USD price of a cryptocurrency. "
                "Input should be the coin name (e.g. 'bitcoin')."
            ),
        ),
        Tool(
            name="get_nft_floor_price",
            func=None,
            coroutine=get_nft_floor_price_tool,
            args_schema=_NFTNameArgs,
            description=(
                "Fetch the floor price of an NFT collection in USD. "
                "Input should be the NFT name or slug."
            ),
        ),
        Tool(
            name="get_protocol_tvl",
            func=None,
            coroutine=get_protocol_total_value_locked_tool,
            args_schema=_ProtocolNameArgs,
            description=(
                "Returns the Total Value Locked (TVL) of a DeFi protocol. "
                "Input is the protocol name."
            ),
        ),
        Tool(
            name="get_fully_diluted_valuation",
            func=None,
            coroutine=get_fully_diluted_valuation_tool,
            args_schema=_CoinNameArgs,
            description=(
                "Get a coin's fully diluted valuation in USD. "
                "Input the coin's name."
            ),
        ),
        Tool(
            name="get_market_cap",
            func=None,
            coroutine=get_coin_market_cap_tool,
            args_schema=_CoinNameArgs,
            description=(
                "Retrieve the market capitalization of a coin in USD. "
                "Input is the coin's name."
            ),
        ),
    ]
