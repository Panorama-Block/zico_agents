import logging
import requests
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
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
    vectorizer = TfidfVectorizer()
    sentence_vectors = vectorizer.fit_transform(data)
    text_vector = vectorizer.transform([text])

    # Compute cosine similarity between input and all candidates
    similarity_scores = cosine_similarity(text_vector, sentence_vectors)

    # Pick top 20 indices, then filter by threshold
    top_indices = similarity_scores.argsort()[0][-20:]
    top_matches = [data[i] for i in top_indices if similarity_scores[0][i] > 0.5]
    return top_matches


def get_coingecko_id(text: str, type: str = "coin") -> str | None:
    """
    Look up the CoinGecko internal ID for a coin or NFT by name.

    Args:
        text: Human-readable coin or NFT name or slug.
        type: Either 'coin' or 'nft'.

    Returns:
        The CoinGecko ID string, or None if not found.

    Raises:
        ValueError if `type` is invalid, or propagates request exceptions.
    """
    url = f"{Config.COINGECKO_BASE_URL}/search"
    params = {"query": text}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if type == "coin":
            return data["coins"][0]["id"] if data["coins"] else None
        elif type == "nft":
            return data.get("nfts", [])[0].get("id") if data.get("nfts") else None
        else:
            raise ValueError("Invalid type specified")

    except requests.exceptions.RequestException as e:
        logging.error(f"API request failed: {e}")
        raise


def get_tradingview_symbol(coingecko_id: str) -> str | None:
    """
    Convert a CoinGecko coin ID into a TradingView ticker symbol.

    Args:
        coingecko_id: The CoinGecko coin ID.

    Returns:
        A string like 'CRYPTO:BTCUSD', or None if symbol is missing.
    """
    url = f"{Config.COINGECKO_BASE_URL}/coins/{coingecko_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        symbol = response.json().get("symbol", "").upper()
        return f"CRYPTO:{symbol}USD" if symbol else None
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get TradingView symbol: {e}")
        raise


def get_price(coin: str) -> float | None:
    """
    Fetch the current USD price of a cryptocurrency.

    Args:
        coin: Human-readable coin name (e.g. 'bitcoin').

    Returns:
        Price in USD as a float, or None if coin not found.
    """
    coin_id = get_coingecko_id(coin, type="coin")
    if not coin_id:
        return None

    url = f"{Config.COINGECKO_BASE_URL}/simple/price"
    params = {"ids": coin_id, "vs_currencies": "USD"}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()[coin_id]["usd"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve price: {e}")
        raise


def get_floor_price(nft: str) -> float | None:
    """
    Retrieve the floor price in USD for an NFT collection.

    Args:
        nft: The NFT collection name or slug.

    Returns:
        Floor price in USD, or None if not found.
    """
    nft_id = get_coingecko_id(nft, type="nft")
    if not nft_id:
        return None

    url = f"{Config.COINGECKO_BASE_URL}/nfts/{nft_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()["floor_price"]["usd"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve floor price: {e}")
        raise


def get_fdv(coin: str) -> float | None:
    """
    Get a coin's Fully Diluted Valuation (FDV) in USD from CoinGecko.

    Args:
        coin: Coin name or slug.

    Returns:
        FDV in USD, or None if not available.
    """
    coin_id = get_coingecko_id(coin, type="coin")
    if not coin_id:
        return None

    url = f"{Config.COINGECKO_BASE_URL}/coins/{coin_id}"
    try:
        data = requests.get(url).json()
        return data.get("market_data", {}).get("fully_diluted_valuation", {}).get("usd")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve FDV: {e}")
        raise


def get_market_cap(coin: str) -> float | None:
    """
    Fetch current market capitalization for a coin via CoinGecko.

    Args:
        coin: The coin name or slug.

    Returns:
        Market cap in USD, or None if not found.
    """
    coin_id = get_coingecko_id(coin, type="coin")
    if not coin_id:
        return None

    url = f"{Config.COINGECKO_BASE_URL}/coins/markets"
    params = {"ids": coin_id, "vs_currency": "USD"}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()[0]["market_cap"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve market cap: {e}")
        raise


def get_protocols_list() -> tuple[list[str], list[str], list[str]]:
    """
    Pull the full list of DeFi protocols from DefiLlama.

    Returns:
        - slugs: List of protocol slugs (for TVL lookup)
        - names: Human-readable names
        - gecko_ids: CoinGecko IDs for integration
    """
    url = f"{Config.DEFILLAMA_BASE_URL}/protocols"
    try:
        data = requests.get(url).json()
        slugs = [item["slug"] for item in data]
        names = [item["name"] for item in data]
        gecko_ids = [item["gecko_id"] for item in data]
        return slugs, names, gecko_ids
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve protocols list: {e}")
        raise


def get_tvl_value(protocol_id: str) -> float:
    """
    Query DefiLlama for a single protocol's TVL.

    Args:
        protocol_id: The slug identifier for the protocol.

    Returns:
        TVL value (could be a dict or number depending on API).
    """
    url = f"{Config.DEFILLAMA_BASE_URL}/chains"
    try:
        print(f"URL: {url}")
        response = requests.get(url)
        print(f"Response: {response.json()}")
        response.raise_for_status()
        chains = response.json()
        chain = next((c for c in chains if c["name"].lower() == protocol_id.lower()), None)
        print(f"Chain: {chain}")
        return chain["tvl"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve protocol TVL: {e}")
        raise


def get_protocol_tvl(protocol_name: str) -> dict[str, float] | None:
    """
    Get a protocol's TVL by name, using fuzzy matching if needed.

    1. Try exact match via CoinGecko ID → DefiLlama slug
    2. If no exact match, find closest names via TF-IDF
    3. Return the highest TVL among matches
    """
    slugs, names, gecko_ids = get_protocols_list()
    tag = get_coingecko_id(protocol_name)
    protocol_id = None

    if tag:
        # map gecko_id to DefiLlama slug
        protocol_id = next((s for s, g in zip(slugs, gecko_ids) if g == tag), None)
        if protocol_id:
            return {tag: get_tvl_value(protocol_id)}

    # fallback: fuzzy text matching on protocol names
    matches = get_most_similar(protocol_name, names)
    if not matches:
        return None

    # fetch TVL for each matched name, pick the highest
    results = []
    for name in matches:
        pid = next(s for s, n in zip(slugs, names) if n == name)
        tvl = get_tvl_value(pid)
        results.append({pid: tvl})

    return max(results, key=lambda d: next(iter(d.values())))


# -----------------------------------------------------------------------------
# Tool wrappers: these catch errors, format responses, and produce strings
# -----------------------------------------------------------------------------

def _append_coin_metadata_suffix(text: str, coin_name: str) -> str:
    """
    Append a structured metadata sentinel to a human-friendly text response.
    Includes CoinGecko coinId and uppercased symbol when available.
    """
    try:
        coin_id = get_coingecko_id(coin_name, type="coin")
        if not coin_id:
            return text
        tv_symbol = get_tradingview_symbol(coin_id)
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


def get_coin_price_tool(coin_name: str) -> dict:
    """ 
    LangChain Tool: Return a user-friendly string with the coin's USD price.
    """
    try:
        price = get_price(coin_name)
        if price is None:
            return Config.PRICE_FAILURE_MESSAGE
        text = Config.PRICE_SUCCESS_MESSAGE.format(coin_name=coin_name, price=price)
        # compute metadata out-of-band
        meta = {}
        try:
            coin_id = get_coingecko_id(coin_name, type="coin")
            if coin_id:
                tv_symbol = get_tradingview_symbol(coin_id)
                meta["coinId"] = tv_symbol # return the symbol as the coinId
                metadata.set_crypto_data_agent(meta)
        except Exception:
            pass

        return {"text": text, "metadata": meta}
    except requests.exceptions.RequestException:
        return {"text": Config.API_ERROR_MESSAGE, "metadata": {}}


def get_nft_floor_price_tool(nft_name: str) -> str:
    """
    LangChain Tool: Return a user-friendly string with the NFT floor price.
    """
    try:
        floor_price = get_floor_price(nft_name)
        if floor_price is None:
            return Config.FLOOR_PRICE_FAILURE_MESSAGE
        return Config.FLOOR_PRICE_SUCCESS_MESSAGE.format(nft_name=nft_name, floor_price=floor_price)
    except requests.exceptions.RequestException:
        return Config.API_ERROR_MESSAGE


def get_protocol_total_value_locked_tool(protocol_name: str) -> str:
    """
    LangChain Tool: Return formatted TVL information for a DeFi protocol.
    """
    try:
        tvl = get_protocol_tvl(protocol_name)
        if tvl is None:
            return Config.TVL_FAILURE_MESSAGE
        tag, tvl_value = next(iter(tvl.items()))
        return Config.TVL_SUCCESS_MESSAGE.format(protocol_name=protocol_name, tvl=tvl_value)
    except requests.exceptions.RequestException:
        return Config.API_ERROR_MESSAGE


def get_fully_diluted_valuation_tool(coin_name: str) -> str:
    """
    LangChain Tool: Return a formatted string with the coin's FDV.
    """
    try:
        fdv = get_fdv(coin_name)
        if fdv is None:
            return Config.FDV_FAILURE_MESSAGE
        text = Config.FDV_SUCCESS_MESSAGE.format(coin_name=coin_name, fdv=fdv)
        return _append_coin_metadata_suffix(text, coin_name)
    except requests.exceptions.RequestException:
        return Config.API_ERROR_MESSAGE


def get_coin_market_cap_tool(coin_name: str) -> str:
    """
    LangChain Tool: Return a formatted string with the coin's market cap.
    """
    try:
        market_cap = get_market_cap(coin_name)
        if market_cap is None:
            return Config.MARKET_CAP_FAILURE_MESSAGE
        text = Config.MARKET_CAP_SUCCESS_MESSAGE.format(coin_name=coin_name, market_cap=market_cap)
        return _append_coin_metadata_suffix(text, coin_name)
    except requests.exceptions.RequestException:
        return Config.API_ERROR_MESSAGE


def get_tools() -> list[Tool]:
    """
    Build and return the list of LangChain Tools for use in an agent.

    Each Tool wraps one of the user-facing helper functions above.
    """

    return [
        Tool(
            name="get_coin_price",
            func=get_coin_price_tool,
            description=(
                "Use this to get the current USD price of a cryptocurrency. "
                "Input should be the coin name (e.g. 'bitcoin')."
            ),
        ),
        Tool(
            name="get_nft_floor_price",
            func=get_nft_floor_price_tool,
            description=(
                "Fetch the floor price of an NFT collection in USD. "
                "Input should be the NFT name or slug."
            ),
        ),
        Tool(
            name="get_protocol_tvl",
            func=get_protocol_total_value_locked_tool,
            description=(
                "Returns the Total Value Locked (TVL) of a DeFi protocol. "
                "Input is the protocol name."
            ),
        ),
        Tool(
            name="get_fully_diluted_valuation",
            func=get_fully_diluted_valuation_tool,
            description=(
                "Get a coin's fully diluted valuation in USD. "
                "Input the coin's name."
            ),
        ),
        Tool(
            name="get_market_cap",
            func=get_coin_market_cap_tool,
            description=(
                "Retrieve the market capitalization of a coin in USD. "
                "Input is the coin's name."
            ),
        ),
    ]