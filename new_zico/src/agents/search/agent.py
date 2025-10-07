import logging
from langgraph.prebuilt import create_react_agent

from src.agents.search.tools import get_tools

logger = logging.getLogger(__name__)


class SearchAgent:
    """Agent dedicated to answering queries via web search tools."""

    def __init__(self, llm):
        self.llm = llm
        tools = get_tools()
        if not tools:
            logger.warning("Search agent initialised without tools; it will act as a plain LLM.")
        self.agent = create_react_agent(
            model=llm,
            tools=tools,
            name="search_agent",
        )
