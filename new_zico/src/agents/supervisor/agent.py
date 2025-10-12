from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langgraph_supervisor import create_supervisor
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from src.agents.config import Config
from typing import TypedDict, Literal, List, Any, Tuple, Optional
import re
import json
from src.agents.metadata import metadata
from src.agents.crypto_data.config import Config as CryptoConfig

# Agents
from src.agents.crypto_data.agent import CryptoDataAgent
from src.agents.database.agent import DatabaseAgent
from src.agents.default.agent import DefaultAgent
from src.agents.swap.agent import SwapAgent
from src.agents.swap.tools import swap_session
from src.agents.swap.prompt import SWAP_AGENT_SYSTEM_PROMPT
from src.agents.search.agent import SearchAgent
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
        available_agents_text = (
            "- crypto_agent: Handles cryptocurrency-related queries like price checks, market data, NFT floor prices, DeFi protocol TVL (don't route to this agent if none of the mention information).\n"
        )

        # Conditionally include database agent
        if is_database_available():
            databaseAgent = DatabaseAgent(llm)
            agents.append(databaseAgent)
            available_agents_text += (
                "- database_agent: Handles database queries and data analysis. Can search and analyze data from the database.\n"
            )
        else:
            databaseAgent = None

        swapAgent = SwapAgent(llm)
        self.swap_agent = swapAgent.agent
        agents.append(self.swap_agent)
        available_agents_text += (
            "- swap_agent: Handles swap operations on the Avalanche network and any other swap question related.\n"
        )

        searchAgent = SearchAgent(llm)
        self.search_agent = searchAgent.agent
        agents.append(self.search_agent)
        available_agents_text += (
            "- search_agent: Uses web search tools for current events and factual lookups.\n"
        )

        defaultAgent = DefaultAgent(llm)
        self.default_agent = defaultAgent.agent
        agents.append(self.default_agent)

        # Track known agent names for response extraction
        self.known_agent_names = {"crypto_agent", "database_agent", "swap_agent", "search_agent", "default_agent"}
        self.specialized_agents = {"crypto_agent", "database_agent", "swap_agent", "search_agent"}
        self.failure_markers = (
            "cannot fulfill",
            "can't fulfill",
            "cannot assist",
            "can't assist",
            "cannot help",
            "can't help",
            "cannot tell",
            "can't tell",
            "cannot tell you",
            "can't tell you",
            "cannot comply",
            "transfer you",
            "specialized agent",
            "no response available",
            "failed to retrieve",
            "api at the moment",
            "handling your request",
            "crypto_agent is handling",
            "will provide",
            "provide the price",
            "tool error",
            "search service is unavailable",
            "configure tavily_api_key",
            "no results found",
            "unable to",
            "cannot get",
            "can't get",
            "cannot find",
            "can't find",
            "could not find",
            "do not have that information",
            "don't have that information",
            "having trouble",
            "trouble finding",
            "I can only"
        )
        self.config_failure_messages = {
            CryptoConfig.PRICE_FAILURE_MESSAGE.lower(),
            CryptoConfig.FLOOR_PRICE_FAILURE_MESSAGE.lower(),
            CryptoConfig.TVL_FAILURE_MESSAGE.lower(),
            CryptoConfig.FDV_FAILURE_MESSAGE.lower(),
            CryptoConfig.MARKET_CAP_FAILURE_MESSAGE.lower(),
            CryptoConfig.API_ERROR_MESSAGE.lower(),
        }

        self._active_user_id: str | None = None
        self._active_conversation_id: str | None = None

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

        search_instruction = (
            "When the user asks about breaking news, recent developments, or requests a web lookup, delegate to the search_agent first."
        )
        search_examples = (
            "Examples of search queries to delegate:\n"
            "- \"What happened with Bitcoin this week?\"\n"
            "- \"Find the latest Avalanche ecosystem partnerships\"\n"
            "- \"Who just won the most recent Formula 1 race?\"\n"
        )

        # System prompt to guide the supervisor
        system_prompt = f"""You are a helpful supervisor that routes user queries to the appropriate specialized agents.

Available agents:
{available_agents_text}

When a user asks about cryptocurrency prices, market data, NFTs, or DeFi protocols, delegate to the crypto_agent.
{database_instruction}
{search_instruction}
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

When a swap conversation is already underway (the user is still providing swap
details or the swap_agent requested follow-up information), keep routing those
messages to the swap_agent until it has gathered every field and signals the
swap intent is ready.

{database_examples}

{search_examples}

Examples of general queries to handle directly:
- "Hello, how are you?"
- "What's the weather like?"
- "Tell me a joke"
- "What is the biggest poll in Trader Joe?"
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

    def _invoke_swap_agent(self, langchain_messages):
        scoped_messages = [SystemMessage(content=SWAP_AGENT_SYSTEM_PROMPT)]
        scoped_messages.extend(langchain_messages)
        try:
            with swap_session(
                user_id=self._active_user_id,
                conversation_id=self._active_conversation_id,
            ):
                response = self.swap_agent.invoke({"messages": scoped_messages})
        except Exception as exc:
            print(f"Error invoking swap agent directly: {exc}")
            return None

        if not response:
            return None

        agent, text, messages_out = self._extract_response_from_graph(response)
        return agent, text, messages_out

    def _extract_response_from_graph(self, response: Any) -> Tuple[str, str, list]:
        messages_out = response.get("messages", []) if isinstance(response, dict) else []
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
        final_agent = final_agent or "supervisor"
        return final_agent, cleaned_response, messages_out

    def _needs_supervisor_fallback(self, agent_name: str, response_text: str) -> bool:
        if not response_text:
            return agent_name in self.specialized_agents
        lowered = response_text.strip().lower()
        if lowered in self.config_failure_messages:
            return True
        if any(marker in lowered for marker in self.failure_markers):
            return True
        if agent_name in self.specialized_agents and not lowered:
            return True
        return False

    def _run_default_agent(self, langchain_messages: List[Any]) -> Tuple[str | None, str | None, list]:
        if not getattr(self, "default_agent", None):
            return None, None, []
        try:
            fallback_response = self.default_agent.invoke({"messages": langchain_messages})
            print("DEBUG: default agent fallback response", fallback_response)
        except Exception as exc:
            print(f"Error invoking default agent fallback: {exc}")
            return None, None, []
        fallback_agent, fallback_text, fallback_messages = self._extract_response_from_graph(fallback_response)
        if not fallback_agent:
            fallback_agent = "default_agent"
        return fallback_agent, fallback_text, fallback_messages

    def _run_search_agent(self, langchain_messages: List[Any]) -> Tuple[str | None, str | None, list]:
        if not getattr(self, "search_agent", None):
            return None, None, []
        try:
            fallback_response = self.search_agent.invoke({"messages": langchain_messages})
            print("DEBUG: search agent fallback response", fallback_response)
        except Exception as exc:
            print(f"Error invoking search agent fallback: {exc}")
            return None, None, []
        fallback_agent, fallback_text, fallback_messages = self._extract_response_from_graph(fallback_response)
        if not fallback_agent:
            fallback_agent = "search_agent"
        return fallback_agent, fallback_text, fallback_messages

    def _build_metadata(self, agent_name: str, messages_out) -> dict:
        if agent_name == "swap_agent":
            swap_meta = metadata.get_swap_agent(
                user_id=self._active_user_id,
                conversation_id=self._active_conversation_id,
            )
            if swap_meta:
                history = metadata.get_swap_history(
                    user_id=self._active_user_id,
                    conversation_id=self._active_conversation_id,
                )
                if history:
                    swap_meta = swap_meta.copy()
                    swap_meta.setdefault("history", history)
                else:
                    swap_meta = swap_meta.copy()
            return swap_meta if swap_meta else {}
        if agent_name == "crypto_agent":
            tool_meta = self._collect_tool_metadata(messages_out)
            if tool_meta:
                metadata.set_crypto_data_agent(tool_meta)
            return metadata.get_crypto_data_agent() or {}
        return {}

    def invoke(
        self,
        messages: List[ChatMessage],
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        self._active_user_id = user_id
        self._active_conversation_id = conversation_id
        swap_state = metadata.get_swap_agent(user_id=user_id, conversation_id=conversation_id)

        langchain_messages = []
        for msg in messages:
            if msg.get("role") == "user":
                langchain_messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "system":
                langchain_messages.append(SystemMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                langchain_messages.append(AIMessage(content=msg.get("content", "")))

        if swap_state and swap_state.get("status") == "collecting":
            swap_result = self._invoke_swap_agent(langchain_messages)
            if swap_result:
                final_agent, cleaned_response, messages_out = swap_result
                meta = self._build_metadata(final_agent, messages_out)
                self._active_user_id = None
                self._active_conversation_id = None
                return {
                    "messages": messages_out,
                    "agent": final_agent,
                    "response": cleaned_response or "Sorry, no meaningful response was returned.",
                    "metadata": meta,
                }
            # If direct swap invocation failed, fall through to supervisor graph with hints
            next_field = swap_state.get("next_field")
            pending_question = swap_state.get("pending_question")
            guidance_parts = [
                "There is an in-progress token swap intent for this conversation.",
                "Keep routing messages to the swap_agent until the intent is complete unless the user explicitly cancels or changes topic.",
            ]
            if next_field:
                guidance_parts.append(f"The next field to collect is: {next_field}.")
            if pending_question:
                guidance_parts.append(f"Continue the swap flow by asking: {pending_question}")
            guidance_text = " ".join(guidance_parts)
            langchain_messages.insert(0, SystemMessage(content=guidance_text))

        try:
            with swap_session(user_id=user_id, conversation_id=conversation_id):
                response = self.app.invoke({"messages": langchain_messages})
                print("DEBUG: response", response)
        except Exception as e:
            print(f"Error in Supervisor: {e}")
            return {
                "messages": [],
                "agent": "supervisor",
                "response": "Sorry, an error occurred while processing your request."
            }

        final_agent, cleaned_response, messages_out = self._extract_response_from_graph(response)

        if self._needs_supervisor_fallback(final_agent, cleaned_response):
            print("INFO: Fallback triggered for agent", final_agent)
            fallback_agent = None
            fallback_response = None
            fallback_messages: list = []

            if final_agent != "search_agent":
                search_agent, search_response, search_messages = self._run_search_agent(langchain_messages)
                if search_response and not self._needs_supervisor_fallback(search_agent or "search_agent", search_response):
                    fallback_agent = search_agent or "search_agent"
                    fallback_response = search_response
                    fallback_messages = search_messages
                else:
                    fallback_agent = search_agent
                    fallback_response = search_response
                    fallback_messages = search_messages

            if not fallback_response or self._needs_supervisor_fallback(fallback_agent or "", fallback_response):
                default_agent, default_response, default_messages = self._run_default_agent(langchain_messages)
                if default_response:
                    fallback_agent = default_agent or "default_agent"
                    fallback_response = default_response
                    fallback_messages = default_messages

            if fallback_response:
                final_agent = fallback_agent or "default_agent"
                cleaned_response = fallback_response
                messages_out = fallback_messages

        meta = self._build_metadata(final_agent, messages_out)
        print("meta: ", meta)
        print("cleaned_response: ", cleaned_response)
        print("final_agent: ", final_agent)

        self._active_user_id = None
        self._active_conversation_id = None

        return {
            "messages": messages_out,
            "agent": final_agent,
            "response": cleaned_response or "Sorry, no meaningful response was returned.",
            "metadata": meta,
        }
