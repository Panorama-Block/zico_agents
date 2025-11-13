import logging

from langgraph.prebuilt import create_react_agent

from .tools import get_tools

logger = logging.getLogger(__name__)


class DcaAgent:
    """Agent orchestrating DCA consultations and workflow confirmation."""

    def __init__(self, llm):
        self.llm = llm
        self.agent = create_react_agent(
            model=llm,
            tools=get_tools(),
            name="dca_agent",
        )
