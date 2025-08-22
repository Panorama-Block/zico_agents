from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langgraph_supervisor import create_supervisor
from src.agents.config import Config
from typing import TypedDict, Literal, List, Any
import re
import json
from src.agents.metadata import metadata

# Agents
from src.agents.crypto_data.agent import CryptoDataAgent
from src.agents.database.agent import DatabaseAgent
from src.agents.default.agent import DefaultAgent
from src.agents.swap.agent import SwapAgent
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

        swapAgent = SwapAgent(llm)
        agents.append(swapAgent.agent)
        available_agents_text += "- swap_agent: Handles swap operations on the Avalanche network and any other swap question related.\n"

        defaultAgent = DefaultAgent(llm)
        agents.append(defaultAgent.agent)

        # Track known agent names for response extraction
        self.known_agent_names = {"crypto_agent", "database_agent", "swap_agent", "default_agent"}

        # Prepare database guidance text to avoid backslashes in f-string expressions
        if databaseAgent:
            database_instruction = "When a user asks for data analysis, database queries, or information from the database, delegate to the database_agent."
            database_examples = (
                "Examples of database queries to delegate:\n"
                "- \"What are the avax chains?\"\n"
                "- \"What information is available about the AVAX in the database agent?\"\n"
                "- \"What is the total number of activities addresses in AVAX?\"\n"
                "- \"How many transactions are there in the AVAX network?\"\n"
            )
        else:
            database_instruction = "Do not delegate to a database agent; answer best-effort without DB access or ask the user to start the database."
            database_examples = ""

        # System prompt to guide the supervisor
        system_prompt = f"""You are a helpful supervisor that routes user queries to the appropriate specialized agents.

Available agents:
{available_agents_text}

When a user asks about cryptocurrency prices, market data, NFTs, or DeFi protocols, delegate to the crypto_agent.
{database_instruction}
For all other queries, respond directly as a helpful assistant.

IMPORTANT: your final response should answer the user's query. Use the agents response to answer the user's query if necessary. Avoid returning control-transfer notes like 'Transferring back to supervisor' — return the substantive answer instead.

Examples of crypto queries to delegate:
- "What is the price of ETH?"
- "What's the market cap of Bitcoin?"
- "What's the floor price of Bored Apes?"
- "What's the TVL of Uniswap?"

Examples of swap queries to delegate:
- I wanna make a swap
- What are the available tokens for swapping?
- I want to swap 100 USD for AVAX

{database_examples}

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

    def _is_handoff_text(self, text: str) -> bool:
        if not text:
            return False
        t = text.strip().lower()
        handoff_keywords = [
            "transferring back",
            "transfer back",
            "returning control",
            "handoff",
            "handing back",
            "delegating back",
            "delegate back",
            "passing back",
            "routing back",
            "route back",
            "back to supervisor",
            "supervisor will handle",
            "sending back to supervisor",
            "give control back",
            "control back to supervisor",
        ]
        return any(k in t for k in handoff_keywords)

    def _sanitize_handoff_phrases(self, text: str) -> str:
        if not text:
            return text
        phrases = [
            "transferring back to supervisor",
            "transfer back to supervisor",
            "returning control to supervisor",
            "handing back to supervisor",
            "delegating back to supervisor",
            "delegate back to supervisor",
            "passing back to supervisor",
            "routing back to supervisor",
            "route back to supervisor",
            "back to supervisor",
            "control back to supervisor",
            "supervisor will handle",
            "sending back to supervisor",
        ]
        sanitized = text
        for p in phrases:
            # remove phrase case-insensitively, with optional surrounding punctuation/whitespace
            pattern = re.compile(r"\b" + re.escape(p) + r"\b[\s\.,;:!\)]*", re.IGNORECASE)
            sanitized = pattern.sub(" ", sanitized)
        # Normalize whitespace
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        return sanitized

    def _get_text_content(self, message: Any) -> str | None:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            collected: List[str] = []
            for part in content:
                # Try dict form first
                if isinstance(part, dict):
                    text = part.get("text") or part.get("content")
                    if isinstance(text, str) and text.strip():
                        collected.append(text.strip())
                else:
                    # Best-effort: objects with 'text' attribute
                    text_attr = getattr(part, "text", None)
                    if isinstance(text_attr, str) and text_attr.strip():
                        collected.append(text_attr.strip())
            if collected:
                return " ".join(collected)
        return None
    
    def _extract_payload(self, text: str) -> tuple[dict, str]:
        # Try JSON payload first
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and "metadata" in obj and "text" in obj:
                return (obj.get("metadata") or {}), str(obj.get("text") or "")
        except Exception:
            pass
        # Fallback to sentinel
        m = re.search(r"\|\|META:\s*(\{.*?\})\|\|", text)
        if m:
            try:
                meta = json.loads(m.group(1))
            except Exception:
                meta = {}
            cleaned = (text[:m.start()] + text[m.end():]).strip()
            cleaned = re.sub(r"\s+", " ", cleaned)
            return meta, cleaned
        return {}, text

    def _collect_tool_metadata(self, messages_out) -> dict:
        # Prefer last tool-ish content with metadata
        for m in reversed(messages_out):
            t = self._get_text_content(m) or ""
            meta, _ = self._extract_payload(t)
            if meta:
                return meta
            # Optional: artifact support if your langchain version has it
            art = getattr(m, "artifact", None)
            if isinstance(art, dict) and art:
                return art
        return {}

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

        # Prefer the last specialized agent message over any router/supervisor meta message
        final_response = None
        final_agent = "supervisor"

        def choose_content_from_message(m) -> tuple[str | None, str | None]:
            print("m: ", m)
            agent_name = getattr(m, "name", None)
            content_text = self._get_text_content(m)
            if not content_text:
                return None, None
            sanitized = self._sanitize_handoff_phrases(content_text)
            if sanitized and sanitized.strip() and not self._is_handoff_text(sanitized):
                # Prefer sanitized content
                return sanitized, agent_name
            return None, None
        

        # 1) Try to find the last message from a known specialized agent that is not a handoff/route-back note
        for m in reversed(messages_out):
            agent_name = getattr(m, "name", None)
            if agent_name in self.known_agent_names:
                content, agent = choose_content_from_message(m)
                if content:
                    final_response = content
                    final_agent = agent or agent_name
                    print(f'agent: {agent_name} content: {content}')
                    break

        # 2) Fallback: any last message with content that is not a handoff note
        if final_response is None:
            for m in reversed(messages_out):
                content, agent = choose_content_from_message(m)
                if content:
                    final_response = content
                    if agent:
                        final_agent = agent
                    break

        # 3) Last resort: use dict-level fields if present
        if final_response is None:
            if isinstance(response, dict):
                final_response = response.get("response") or "No response available"
                final_agent = response.get("agent", final_agent)
            else:
                final_response = "No response available"

        cleaned_response = final_response or "Sorry, no meaningful response was returned."
        meta = {}
        if final_agent == "swap_agent":
            meta = {'src': 'AVAX', 'dst': 'USDC', 'amount': '100'}
        elif final_agent == "crypto_agent":
            meta = metadata.get_crypto_data_agent() or {}
        else:
            meta = {}
        print("meta: ", meta)
        print("cleaned_response: ", cleaned_response)

        print("final_agent: ", final_agent)

        return {
            "messages": messages_out,
            "agent": final_agent,
            "response": cleaned_response or "Sorry, no meaningful response was returned.",
            "metadata": meta,
        }