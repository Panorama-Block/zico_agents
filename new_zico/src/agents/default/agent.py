from langgraph.prebuilt import create_react_agent

class DefaultAgent():
    """Agent for handling default queries and data retrieval."""

    def __init__(self, llm):
        self.llm = llm

        self.agent = create_react_agent(
            model=llm,
            tools=[],
            name="default_agent"
        )
