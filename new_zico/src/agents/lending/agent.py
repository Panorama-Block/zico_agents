import logging
from src.agents.lending.tools import get_tools
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)


class LendingAgent:
    """Agent for handling lending operations (supply, borrow, repay, withdraw)."""
    def __init__(self, llm):
        self.llm = llm
        self.agent = create_react_agent(
            model=llm,
            tools=get_tools(),
            name="lending_agent"
        )
