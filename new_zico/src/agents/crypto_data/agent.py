import logging
from src.agents.crypto_data.tools import get_tools
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)


class CryptoDataAgent():
    """Agent for handling cryptocurrency-related queries and data retrieval."""

    def __init__(self, llm):
        self.llm = llm

        self.agent = create_react_agent(
            model=llm,
            tools=get_tools(),
            name="crypto_agent"
        )


