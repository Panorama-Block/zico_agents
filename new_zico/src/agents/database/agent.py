from src.agents.database.tools import get_tools
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableConfig
from datetime import datetime
from typing import List, Any
from src.agents.database.tools import call_tool

SYSTEM_PROMPT = """
You are a senior data assistant specializing in ClickHouse. Your role is to help users query a database related to the Avalanche (AVAX) blockchain network using natural language.

You should:
- Interpret user questions.
- Explore the database using tools (e.g., list_tables, describe_table, sample_table).
- Strategically decide which tools to call and when.
- Generate efficient and accurate SQL queries.
- Summarize and explain the query results in business-friendly language.

## 🧠 STRATEGIC THINKING (BEFORE ACTING)
- Before calling tools, reason step-by-step.
- Identify what information is missing.
- Formulate a plan to investigate the schema or validate assumptions.
- Only execute SQL after validating the database structure.

## 🔧 TOOL USAGE RULES
- Always include a clear and thoughtful `reasoning` parameter for every tool call.
- Ensure all required parameters are included and accurate.
- Use tools sparingly and with purpose. Avoid unnecessary calls.
- Do not repeat tool calls. After receiving a response, do not call the same tool again unless the user asks for more information.

## 🗃️ DATABASE CONTEXT
- All data is related to the Avalanche (AVAX) blockchain.
- Tables may include smart contracts, transactions, wallet addresses, gas fees, staking, governance, and on-chain activity.

## 📊 OUTPUT FORMAT
- Always respond in string format.
- Use bullet points when presenting structured data.
- If the query involves multiple steps or complex logic, break it down for the user.
- Assume the user is a **business analyst** or **data scientist** who does **not know SQL**.

## 🎯 GOAL
Transform a vague user request into:
1. A strategic plan.
2. The right tool calls to understand the database.
3. An optimized SQL query.
4. A clear, insightful explanation of the results.

Today’s date is {datetime.now().strftime('%Y-%m-%d')}.
""".strip()


class DatabaseAgent(Runnable):
    """Agent for handling database queries."""

    def __init__(self, llm, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self.llm = llm.bind_tools(get_tools())
        self.name = "database_agent"

    def create_history(self) -> List[BaseMessage]:
        """Create a history of messages for the agent."""
        return [
            SystemMessage(content=SYSTEM_PROMPT),
        ]

    def invoke(self, input: Any, config: RunnableConfig = None) -> str:
        try:
            """Process the input, which can be a dict or a list of messages."""
            # 🔧 Suporte tanto para dict com chave "messages" quanto para lista direta
            if isinstance(input, dict) and "messages" in input:
                user_messages = input["messages"]
            elif isinstance(input, list):
                user_messages = input
            else:
                raise ValueError("Invalid input format. Expected dict with 'messages' or a list of messages.")

            n_iterations = 0
            messages = self.create_history() + user_messages  # ✅ inclui o system prompt no histórico

            # initial_response = self.llm.invoke(messages)
            # return {
            #     "messages": initial_response,
            #     "agent": self.name
            # }

            while n_iterations < self.max_iterations:
                response = self.llm.invoke(messages)
                print("response", response)
                messages.append(response)
                if not response.tool_calls:
                    final_response = {
                        "messages": messages,
                        "agent": self.name
                    }
                    print("DEBUG: final_response", final_response)
                    return final_response
                for tool_call in response.tool_calls:
                    tool_result = call_tool(tool_call)
                    messages.append(tool_result)
                n_iterations += 1

            return response.content
        except Exception as e:
            print(f"Error in DatabaseAgent: {e}")
            return "Sorry, an error occurred while processing your request."
 

