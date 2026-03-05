import logging

from langgraph.prebuilt import create_react_agent

from .tools import get_tools
from src.agents.portfolio.tools import get_user_portfolio_tool

logger = logging.getLogger(__name__)


class DcaAgent:
    """Agent orchestrating DCA consultations and workflow confirmation."""

    def __init__(self, llm):
        self.llm = llm
        self.agent = create_react_agent(
            model=llm,
            tools=get_tools() + [get_user_portfolio_tool],
            name="dca_agent",
        )
