import logging
from src.agents.staking.tools import get_tools
from src.agents.portfolio.tools import get_user_portfolio_tool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)


class StakingAgent:
    """Agent for handling staking operations (stake ETH, unstake stETH) via Lido on Ethereum."""
    def __init__(self, llm):
        self.llm = llm
        self.agent = create_react_agent(
            model=llm,
            tools=get_tools() + [get_user_portfolio_tool],
            name="staking_agent"
        )
