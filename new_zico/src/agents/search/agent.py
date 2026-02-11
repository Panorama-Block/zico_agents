import logging
from langgraph.prebuilt import create_react_agent

from src.agents.search.tools import get_tools
from src.agents.markdown_instructions import MARKDOWN_INSTRUCTIONS

logger = logging.getLogger(__name__)

SEARCH_SYSTEM_PROMPT = f"""You are Zico's web search specialist.
You find and summarize the latest information from the web to answer user questions about current events, crypto news, regulations, and factual lookups.

Always respond in English, regardless of the user's language.

Rules:
- Always use your search tools to find current information. Never make up facts.
- Cite sources when presenting specific claims or data points.
- Summarize findings clearly and concisely, highlighting the most relevant information first.
- If search results are inconclusive, say so and suggest alternative search terms.
{MARKDOWN_INSTRUCTIONS}"""


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
            prompt=SEARCH_SYSTEM_PROMPT,
        )
