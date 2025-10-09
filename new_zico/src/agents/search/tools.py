
import logging
import os
from typing import List

from langchain_core.tools import Tool

logger = logging.getLogger(__name__)


def _build_tavily_tool():
    """Create a Tavily search tool if the dependency and API key are available."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.warning("TAVILY_API_KEY not set; web search tool disabled.")
        return None

    try:
        from langchain_tavily import TavilySearch
    except ImportError as exc:  # pragma: no cover - dependency may be optional
        logger.warning("langchain_tavily package is unavailable: %s", exc)
        return None

    try:
        # TavilySearch currently expects the API key either via keyword or env var.
        try:
            return TavilySearch(api_key=api_key)
        except TypeError:
            return TavilySearch(tavily_api_key=api_key)
    except Exception as exc:  # pragma: no cover - runtime init guard
        logger.error("Failed to initialise Tavily search tool: %s", exc)
        return None


def _search_unavailable(query: str) -> str:
    return (
        "Search service is unavailable right now."
        " Configure TAVILY_API_KEY and install langchain-tavily to enable live results."
    )


def get_tools() -> List:
    """Return the toolset used by the search agent."""
    tools = []
    tavily_tool = _build_tavily_tool()
    if tavily_tool:
        tools.append(tavily_tool)
    else:
        tools.append(
            Tool(
                name="search_unavailable",
                func=_search_unavailable,
                description=(
                    "Fallback search stub that informs the user when the web search"
                    " service is not configured."
                ),
            )
        )
    return tools
