import logging
from src.agents.liquidity.tools import get_tools
from src.agents.portfolio.tools import get_user_portfolio_tool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)


class LiquidityAgent:
    """Agent for the `liquidity` capability — handles add/remove LP and claim-rewards intents.

    Provider routing happens at the backend; this agent only emits CapabilityIntent payloads.
    """
    def __init__(self, llm):
        self.llm = llm
        self.agent = create_react_agent(
            model=llm,
            tools=get_tools() + [get_user_portfolio_tool],
            name="liquidity_agent"
        )
