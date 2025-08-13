from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langgraph_supervisor import create_supervisor
from src.agents.config import Config
from typing import TypedDict, Literal, List, Any

# Agents
from src.agents.crypto_data.agent import CryptoDataAgent
from src.agents.database.agent import DatabaseAgent
from src.agents.default.agent import DefaultAgent
from src.agents.database.client import is_database_available

llm = ChatGoogleGenerativeAI(
    model=Config.GEMINI_MODEL,
    temperature=0.7,
    google_api_key=Config.GEMINI_API_KEY
)

embeddings = GoogleGenerativeAIEmbeddings(
    model=Config.GEMINI_EMBEDDING_MODEL,
    google_api_key=Config.GEMINI_API_KEY
)

class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str

class Supervisor:
    def __init__(self, llm):
        self.llm = llm

        cryptoDataAgentClass = CryptoDataAgent(llm)
        cryptoDataAgent = cryptoDataAgentClass.agent

        agents = [cryptoDataAgent]
        available_agents_text = "- crypto_agent: Handles cryptocurrency-related queries like price checks, market data, NFT floor prices, DeFi protocol TVL, etc.\n"

        # Conditionally include database agent
        if is_database_available():
            databaseAgent = DatabaseAgent(llm)
            agents.append(databaseAgent)
            available_agents_text += "- database_agent: Handles database queries and data analysis. Can search and analyze data from the database.\n"
        else:
            databaseAgent = None

        defaultAgent = DefaultAgent(llm)
        agents.append(defaultAgent.agent)

        # System prompt to guide the supervisor
        system_prompt = f"""You are a helpful supervisor that routes user queries to the appropriate specialized agents.

Available agents:
{available_agents_text}

When a user asks about cryptocurrency prices, market data, NFTs, or DeFi protocols, delegate to the crypto_agent.
{"When a user asks for data analysis, database queries, or information from the database, delegate to the database_agent." if databaseAgent else "Do not delegate to a database agent; answer best-effort without DB access or ask the user to start the database."}
For all other queries, respond directly as a helpful assistant.

IMPORTANT: your final response should answer the user's query. Use the agents response to answer the user's query if necessary.

Examples of crypto queries to delegate:
- "What is the price of ETH?"
- "What's the market cap of Bitcoin?"
- "What's the floor price of Bored Apes?"
- "What's the TVL of Uniswap?"

{"Examples of database queries to delegate:\n- \"What are the avax chains?\"\n- \"What information is available about the AVAX in the database agent?\"\n- \"What is the total number of activities addresses in AVAX?\"\n- \"How many transactions are there in the AVAX network?\"\n" if databaseAgent else ""}

Examples of general queries to handle directly:
- "Hello, how are you?"
- "What's the weather like?"
- "Tell me a joke"
"""

        self.supervisor = create_supervisor(
            agents,
            model=llm,
            prompt=system_prompt,
            output_mode="last_message"
        )

        self.app = self.supervisor.compile()

    def invoke(self, messages: List[ChatMessage]) -> dict:
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        langchain_messages = []
        for msg in messages:
            if msg.get("role") == "user":
                langchain_messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "system":
                langchain_messages.append(SystemMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                langchain_messages.append(AIMessage(content=msg.get("content", "")))

        try:
            response = self.app.invoke({"messages": langchain_messages})
            print("DEBUG: response", response)
        except Exception as e:
            print(f"Error in Supervisor: {e}")
            return {
                "messages": [],
                "agent": "supervisor",
                "response": "Sorry, an error occurred while processing your request."
            }

        messages_out = response.get("messages", []) if isinstance(response, dict) else []

        # Safely extract final response content
        final_response = None
        final_agent = "supervisor"

        for m in reversed(messages_out):
            content = getattr(m, "content", None)
            if content:
                final_response = content
                break

        for m in reversed(messages_out):
            agent_name = getattr(m, "name", None)
            if agent_name:
                final_agent = agent_name
                break

        if final_response is None:
            # Fallbacks if structure differs
            if isinstance(response, dict):
                final_response = response.get("response") or "No response available"
            else:
                final_response = "No response available"

        return {
            "messages": messages_out,
            "agent": final_agent,
            "response": final_response or "Sorry, no meaningful response was returned."
        }