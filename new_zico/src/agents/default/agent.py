from langgraph.prebuilt import create_react_agent
from src.agents.markdown_instructions import MARKDOWN_INSTRUCTIONS

DEFAULT_SYSTEM_PROMPT = f"""You are Zico, a friendly and knowledgeable AI assistant specializing in DeFi and cryptocurrency.
You help users understand blockchain concepts, DeFi protocols, and crypto-related topics.

Always respond in English, regardless of the user's language.

Rules:
- Be helpful, concise, and accurate.
- For educational questions, explain concepts clearly with examples when useful.
- If a question is outside your expertise, say so honestly.
- For greetings and simple questions, keep responses brief and friendly.
{MARKDOWN_INSTRUCTIONS}"""


class DefaultAgent():
    """Agent for handling default queries and data retrieval."""

    def __init__(self, llm):
        self.llm = llm

        self.agent = create_react_agent(
            model=llm,
            tools=[],
            name="default_agent",
            prompt=DEFAULT_SYSTEM_PROMPT,
        )
