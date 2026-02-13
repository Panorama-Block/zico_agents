"""
Portfolio Advisor agent — reads wallet holdings and cross-references with
web search to produce risk analysis and swap recommendations.
"""

import logging

from langgraph.prebuilt import create_react_agent

from src.agents.portfolio.prompt import PORTFOLIO_ADVISOR_SYSTEM_PROMPT
from src.agents.portfolio.tools import get_tools as get_portfolio_tools
from src.agents.search.tools import get_tools as get_search_tools

logger = logging.getLogger(__name__)


class PortfolioAdvisorAgent:
    """Agent that analyses on-chain portfolio data and recommends actions."""

    def __init__(self, llm):
        self.llm = llm

        # Combine portfolio tools + search tools so the agent can
        # both read the wallet AND look up recent news for held tokens.
        tools = get_portfolio_tools() + get_search_tools()

        self.agent = create_react_agent(
            model=llm,
            tools=tools,
            name="portfolio_advisor",
            prompt=PORTFOLIO_ADVISOR_SYSTEM_PROMPT,
        )
