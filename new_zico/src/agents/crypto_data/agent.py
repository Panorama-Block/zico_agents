import logging
from src.agents.crypto_data.tools import get_tools
from src.agents.markdown_instructions import MARKDOWN_INSTRUCTIONS
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

CRYPTO_SYSTEM_PROMPT = f"""You are Zico's cryptocurrency data specialist.
You provide accurate, real-time information about cryptocurrency prices, market caps, FDV, TVL, NFT floor prices, and DeFi protocol data.

Always respond in English, regardless of the user's language.

Rules:
- Always use your tools to fetch live data. Never fabricate prices or stats.
- Present data clearly with the token/protocol name, current value, and relevant context.
- When comparing assets, use tables for clarity.
- If a token or protocol is not found, say so clearly and suggest alternatives.
{MARKDOWN_INSTRUCTIONS}"""


class CryptoDataAgent():
    """Agent for handling cryptocurrency-related queries and data retrieval."""

    def __init__(self, llm):
        self.llm = llm

        self.agent = create_react_agent(
            model=llm,
            tools=get_tools(),
            name="crypto_agent",
            prompt=CRYPTO_SYSTEM_PROMPT,
        )
