import logging
from src.agents.swap.tools import get_tools
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)


class SwapAgent:
    """Agent for handling swap operations and any other swap related questions"""
    def __init__(self, llm):
        self.llm = llm
        self.agent = create_react_agent(
            model=llm,
            tools=get_tools(),
            name="swap_agent"
        )