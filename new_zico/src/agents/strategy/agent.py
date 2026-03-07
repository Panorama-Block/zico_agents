"""Strategy agent wrapper."""

from __future__ import annotations

import logging

from langgraph.prebuilt import create_react_agent

from src.agents.portfolio.tools import get_user_portfolio_tool
from src.agents.strategy.tools import get_tools

from .prompt import STRATEGY_AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class StrategyAgent:
    """Agent that orchestrates AVAX strategy recommendation workflows."""

    def __init__(self, llm):
        self.llm = llm
        self.agent = create_react_agent(
            model=llm,
            tools=get_tools() + [get_user_portfolio_tool],
            name="strategy_agent",
            prompt=STRATEGY_AGENT_SYSTEM_PROMPT,
        )
