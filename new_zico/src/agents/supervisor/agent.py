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
from src.agents.swap.config import SwapConfig
from src.agents.swap.tools import swap_session
from src.agents.swap.prompt import SWAP_AGENT_SYSTEM_PROMPT
from src.agents.dca.agent import DcaAgent
from src.agents.dca.tools import dca_session
from src.agents.dca.prompt import DCA_AGENT_SYSTEM_PROMPT
from src.agents.lending.agent import LendingAgent
from src.agents.lending.tools import lending_session
from src.agents.lending.prompt import LENDING_AGENT_SYSTEM_PROMPT
from src.agents.lending.config import LendingConfig
from src.agents.staking.agent import StakingAgent
from src.agents.staking.tools import staking_session
from src.agents.staking.prompt import STAKING_AGENT_SYSTEM_PROMPT
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

        dcaAgent = DcaAgent(llm)
        self.dca_agent = dcaAgent.agent
        agents.append(self.dca_agent)
        available_agents_text += (
            "- dca_agent: Plans DCA swap workflows, consulting strategy docs, validating parameters, and confirming automation metadata.\n"
        )

        lendingAgent = LendingAgent(llm)
        self.lending_agent = lendingAgent.agent
        agents.append(self.lending_agent)
        available_agents_text += (
            "- lending_agent: Handles lending operations (supply, borrow, repay, withdraw) on DeFi protocols like Aave.\n"
        )

        stakingAgent = StakingAgent(llm)
        self.staking_agent = stakingAgent.agent
        agents.append(self.staking_agent)
        available_agents_text += (
            "- staking_agent: Handles staking operations (stake ETH, unstake stETH) via Lido on Ethereum.\n"
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
        self.known_agent_names = {"crypto_agent", "database_agent", "swap_agent", "dca_agent", "lending_agent", "staking_agent", "search_agent", "default_agent"}
        self.specialized_agents = {"crypto_agent", "database_agent", "swap_agent", "dca_agent", "lending_agent", "staking_agent", "search_agent"}
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

Always respond in English, even if the user communicates in another language.

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

Examples of dca queries to delegate:
- Help me schedule a daily DCA from USDC to AVAX
- Suggest a weekly swap DCA strategy
- I want to automate a monthly swap from token A to token B

Examples of lending queries to delegate:
- I want to supply USDC
- I want to borrow ETH on Arbitrum
- Help me with a lending operation
- I want to make a supply of 100 USDC
- Withdraw my WETH from the lending protocol

Examples of staking queries to delegate:
- I want to stake ETH
- I want to stake 2 ETH on Lido
- Help me unstake my stETH
- I want to earn staking rewards
- Convert my ETH to stETH

When a swap conversation is already underway (the user is still providing swap
details or the swap_agent requested follow-up information), keep routing those
messages to the swap_agent until it has gathered every field and signals the
swap intent is ready.

When a DCA conversation is already underway (the user is reviewing strategy recommendations or adjusting schedule parameters), keep routing messages to the dca_agent until the workflow is confirmed or cancelled.

When a lending conversation is already underway (the user is providing lending details like asset, amount, network), keep routing messages to the lending_agent until the lending intent is ready or cancelled.

When a staking conversation is already underway (the user is providing staking details like action or amount), keep routing messages to the staking_agent until the staking intent is ready or cancelled.

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

        self._swap_network_terms, self._swap_token_terms = self._build_swap_detection_terms()
        self._lending_network_terms, self._lending_asset_terms = self._build_lending_detection_terms()

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

    def _invoke_dca_agent(self, langchain_messages):
        scoped_messages = [SystemMessage(content=DCA_AGENT_SYSTEM_PROMPT)]
        scoped_messages.extend(langchain_messages)
        try:
            with dca_session(
                user_id=self._active_user_id,
                conversation_id=self._active_conversation_id,
            ):
                response = self.dca_agent.invoke({"messages": scoped_messages})
        except Exception as exc:
            print(f"Error invoking dca agent directly: {exc}")
            return None

        if not response:
            return None

        agent, text, messages_out = self._extract_response_from_graph(response)
        return agent, text, messages_out

    def _invoke_lending_agent(self, langchain_messages):
        scoped_messages = [SystemMessage(content=LENDING_AGENT_SYSTEM_PROMPT)]
        scoped_messages.extend(langchain_messages)
        try:
            with lending_session(
                user_id=self._active_user_id,
                conversation_id=self._active_conversation_id,
            ):
                response = self.lending_agent.invoke({"messages": scoped_messages})
        except Exception as exc:
            print(f"Error invoking lending agent directly: {exc}")
            return None

        if not response:
            return None

        agent, text, messages_out = self._extract_response_from_graph(response)
        return agent, text, messages_out

    def _invoke_staking_agent(self, langchain_messages):
        scoped_messages = [SystemMessage(content=STAKING_AGENT_SYSTEM_PROMPT)]
        scoped_messages.extend(langchain_messages)
        try:
            with staking_session(
                user_id=self._active_user_id,
                conversation_id=self._active_conversation_id,
            ):
                response = self.staking_agent.invoke({"messages": scoped_messages})
        except Exception as exc:
            print(f"Error invoking staking agent directly: {exc}")
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

    def _detect_pending_followups(self, messages: List[Any]) -> tuple[bool, bool]:
        awaiting_swap = False
        awaiting_dca = False
        def _get_entry_value(entry: Any, dict_keys: tuple[str, ...], attr_name: str) -> Any:
            """Support both camelCase (gateway) and snake_case (local) message fields."""
            if isinstance(entry, dict):
                for key in dict_keys:
                    if key in entry:
                        return entry.get(key)
                return None
            return getattr(entry, attr_name, None)

        for entry in reversed(messages):
            role_raw = _get_entry_value(entry, ("role", "Role"), "role")
            agent_label_raw = _get_entry_value(entry, ("agent_name", "agentName"), "agent_name")
            action_type_raw = _get_entry_value(entry, ("action_type", "actionType"), "action_type")
            requires_action_raw = _get_entry_value(
                entry,
                ("requires_action", "requiresAction"),
                "requires_action",
            )
            metadata_payload = _get_entry_value(entry, ("metadata",), "metadata") or {}

            role = str(role_raw or "").lower()
            if role != "assistant":
                continue
            agent_label = str(agent_label_raw or "").lower()
            action_type = str(action_type_raw or "").lower()
            requires_action = bool(requires_action_raw)
            status = str((metadata_payload.get("status") if isinstance(metadata_payload, dict) else "") or "").lower()

            if requires_action and status != "ready":
                if action_type == "swap" or "swap" in agent_label:
                    awaiting_swap = True
                if action_type == "dca" or "dca" in agent_label:
                    awaiting_dca = True
            break
        return awaiting_swap, awaiting_dca

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
        if agent_name == "dca_agent":
            dca_meta = metadata.get_dca_agent(
                user_id=self._active_user_id,
                conversation_id=self._active_conversation_id,
            )
            if dca_meta:
                history = metadata.get_dca_history(
                    user_id=self._active_user_id,
                    conversation_id=self._active_conversation_id,
                )
                if history:
                    dca_meta = dca_meta.copy()
                    dca_meta.setdefault("history", history)
                else:
                    dca_meta = dca_meta.copy()
            return dca_meta if dca_meta else {}
        if agent_name == "lending_agent":
            lending_meta = metadata.get_lending_agent(
                user_id=self._active_user_id,
                conversation_id=self._active_conversation_id,
            )
            if lending_meta:
                history = metadata.get_lending_history(
                    user_id=self._active_user_id,
                    conversation_id=self._active_conversation_id,
                )
                if history:
                    lending_meta = lending_meta.copy()
                    lending_meta.setdefault("history", history)
                else:
                    lending_meta = lending_meta.copy()
            return lending_meta if lending_meta else {}
        if agent_name == "staking_agent":
            staking_meta = metadata.get_staking_agent(
                user_id=self._active_user_id,
                conversation_id=self._active_conversation_id,
            )
            if staking_meta:
                history = metadata.get_staking_history(
                    user_id=self._active_user_id,
                    conversation_id=self._active_conversation_id,
                )
                if history:
                    staking_meta = staking_meta.copy()
                    staking_meta.setdefault("history", history)
                else:
                    staking_meta = staking_meta.copy()
            return staking_meta if staking_meta else {}
        if agent_name == "crypto_agent":
            tool_meta = self._collect_tool_metadata(messages_out)
            if tool_meta:
                metadata.set_crypto_data_agent(tool_meta)
            return metadata.get_crypto_data_agent() or {}
        return {}

    def _build_swap_detection_terms(self) -> tuple[set[str], set[str]]:
        networks: set[str] = set()
        tokens: set[str] = set()
        try:
            for net in SwapConfig.list_networks():
                lowered = net.lower()
                networks.add(lowered)
                try:
                    for token in SwapConfig.list_tokens(net):
                        tokens.add(token.lower())
                except ValueError:
                    continue
        except Exception:
            return set(), set()
        return networks, tokens

    def _is_swap_like_request(self, messages: List[ChatMessage]) -> bool:
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            lowered = content.lower()
            swap_keywords = (
                "swap",
                "swapping",
                "exchange",
                "convert",
                "trade",
            )
            if not any(keyword in lowered for keyword in swap_keywords):
                return False
            if any(term and term in lowered for term in self._swap_network_terms):
                return True
            if any(term and term in lowered for term in self._swap_token_terms):
                return True
            if "token" in lowered or any(ch.isdigit() for ch in lowered):
                return True
            # Default to True if the user explicitly mentioned swap-related keywords,
            # even if they haven't provided networks/tokens yet.
            return True
        return False

    def _build_lending_detection_terms(self) -> tuple[set[str], set[str]]:
        networks: set[str] = set()
        assets: set[str] = set()
        try:
            for net in LendingConfig.list_networks():
                lowered = net.lower()
                networks.add(lowered)
                try:
                    for asset in LendingConfig.list_assets(net):
                        assets.add(asset.lower())
                except ValueError:
                    continue
        except Exception:
            return set(), set()
        return networks, assets

    def _is_lending_like_request(self, messages: List[ChatMessage]) -> bool:
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            lowered = content.lower()
            lending_keywords = (
                "lend",
                "lending",
                "supply",
                "borrow",
                "repay",
                "withdraw",
                "deposit",
                "aave",
                "compound",
            )
            if not any(keyword in lowered for keyword in lending_keywords):
                return False
            if any(term and term in lowered for term in self._lending_network_terms):
                return True
            if any(term and term in lowered for term in self._lending_asset_terms):
                return True
            if any(ch.isdigit() for ch in lowered):
                return True
            # Default to True if the user explicitly mentioned lending-related keywords
            return True
        return False

    def _is_staking_like_request(self, messages: List[ChatMessage]) -> bool:
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            lowered = content.lower()
            staking_keywords = (
                "stake",
                "staking",
                "unstake",
                "unstaking",
                "steth",
                "lido",
                "liquid staking",
                "staking rewards",
                "eth staking",
            )
            if not any(keyword in lowered for keyword in staking_keywords):
                return False
            # Default to True if the user explicitly mentioned staking-related keywords
            return True
        return False

    def invoke(
        self,
        messages: List[ChatMessage],
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        self._active_user_id = user_id
        self._active_conversation_id = conversation_id
        awaiting_swap, awaiting_dca = self._detect_pending_followups(messages)

        langchain_messages = []
        for msg in messages:
            if msg.get("role") == "user":
                langchain_messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "system":
                langchain_messages.append(SystemMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                langchain_messages.append(AIMessage(content=msg.get("content", "")))

        langchain_messages.insert(
            0,
            SystemMessage(content="Always respond in English, regardless of the user's language."),
        )

        dca_state = metadata.get_dca_agent(user_id=user_id, conversation_id=conversation_id)
        swap_state = metadata.get_swap_agent(user_id=user_id, conversation_id=conversation_id)
        lending_state = metadata.get_lending_agent(user_id=user_id, conversation_id=conversation_id)
        staking_state = metadata.get_staking_agent(user_id=user_id, conversation_id=conversation_id)

        # Check for new staking request first
        if not staking_state and self._is_staking_like_request(messages):
            staking_result = self._invoke_staking_agent(langchain_messages)
            if staking_result:
                final_agent, cleaned_response, messages_out = staking_result
                meta = self._build_metadata(final_agent, messages_out)
                self._active_user_id = None
                self._active_conversation_id = None
                return {
                    "messages": messages_out,
                    "agent": final_agent,
                    "response": cleaned_response or "Sorry, no meaningful response was returned.",
                    "metadata": meta,
                }

        # Check for new lending request
        if not lending_state and self._is_lending_like_request(messages):
            lending_result = self._invoke_lending_agent(langchain_messages)
            if lending_result:
                final_agent, cleaned_response, messages_out = lending_result
                meta = self._build_metadata(final_agent, messages_out)
                self._active_user_id = None
                self._active_conversation_id = None
                return {
                    "messages": messages_out,
                    "agent": final_agent,
                    "response": cleaned_response or "Sorry, no meaningful response was returned.",
                    "metadata": meta,
                }

        if not swap_state and self._is_swap_like_request(messages):
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

        in_progress_statuses = {"consulting", "recommendation", "confirmation"}

        if dca_state and dca_state.get("status") in in_progress_statuses:
            dca_result = self._invoke_dca_agent(langchain_messages)
            if dca_result:
                final_agent, cleaned_response, messages_out = dca_result
                meta = self._build_metadata(final_agent, messages_out)
                self._active_user_id = None
                self._active_conversation_id = None
                return {
                    "messages": messages_out,
                    "agent": final_agent,
                    "response": cleaned_response or "Sorry, no meaningful response was returned.",
                    "metadata": meta,
                }
            stage = dca_state.get("status")
            next_field = dca_state.get("next_field")
            pending_question = dca_state.get("pending_question")
            guidance_parts = [
                "There is an in-progress DCA planning session for this conversation.",
                "Keep routing messages to the dca_agent until the workflow is confirmed or the user cancels.",
            ]
            if stage:
                guidance_parts.append(f"The current stage is: {stage}.")
            if next_field:
                guidance_parts.append(f"The next field to collect is: {next_field}.")
            if pending_question:
                guidance_parts.append(f"Continue the DCA flow by asking: {pending_question}")
            langchain_messages.insert(0, SystemMessage(content=" ".join(guidance_parts)))
        elif awaiting_dca:
            dca_result = self._invoke_dca_agent(langchain_messages)
            if dca_result:
                final_agent, cleaned_response, messages_out = dca_result
                meta = self._build_metadata(final_agent, messages_out)
                self._active_user_id = None
                self._active_conversation_id = None
                return {
                    "messages": messages_out,
                    "agent": final_agent,
                    "response": cleaned_response or "Sorry, no meaningful response was returned.",
                    "metadata": meta,
                }

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
        elif awaiting_swap:
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

        # Handle in-progress lending flow
        if lending_state and lending_state.get("status") == "collecting":
            lending_result = self._invoke_lending_agent(langchain_messages)
            if lending_result:
                final_agent, cleaned_response, messages_out = lending_result
                meta = self._build_metadata(final_agent, messages_out)
                self._active_user_id = None
                self._active_conversation_id = None
                return {
                    "messages": messages_out,
                    "agent": final_agent,
                    "response": cleaned_response or "Sorry, no meaningful response was returned.",
                    "metadata": meta,
                }
            # If direct lending invocation failed, fall through to supervisor graph with hints
            next_field = lending_state.get("next_field")
            pending_question = lending_state.get("pending_question")
            guidance_parts = [
                "There is an in-progress lending intent for this conversation.",
                "Keep routing messages to the lending_agent until the intent is complete unless the user explicitly cancels or changes topic.",
            ]
            if next_field:
                guidance_parts.append(f"The next field to collect is: {next_field}.")
            if pending_question:
                guidance_parts.append(f"Continue the lending flow by asking: {pending_question}")
            guidance_text = " ".join(guidance_parts)
            langchain_messages.insert(0, SystemMessage(content=guidance_text))

        # Handle in-progress staking flow
        if staking_state and staking_state.get("status") == "collecting":
            staking_result = self._invoke_staking_agent(langchain_messages)
            if staking_result:
                final_agent, cleaned_response, messages_out = staking_result
                meta = self._build_metadata(final_agent, messages_out)
                self._active_user_id = None
                self._active_conversation_id = None
                return {
                    "messages": messages_out,
                    "agent": final_agent,
                    "response": cleaned_response or "Sorry, no meaningful response was returned.",
                    "metadata": meta,
                }
            # If direct staking invocation failed, fall through to supervisor graph with hints
            next_field = staking_state.get("next_field")
            pending_question = staking_state.get("pending_question")
            guidance_parts = [
                "There is an in-progress staking intent for this conversation.",
                "Keep routing messages to the staking_agent until the intent is complete unless the user explicitly cancels or changes topic.",
            ]
            if next_field:
                guidance_parts.append(f"The next field to collect is: {next_field}.")
            if pending_question:
                guidance_parts.append(f"Continue the staking flow by asking: {pending_question}")
            guidance_text = " ".join(guidance_parts)
            langchain_messages.insert(0, SystemMessage(content=guidance_text))

        try:
            with swap_session(user_id=user_id, conversation_id=conversation_id):
                with dca_session(user_id=user_id, conversation_id=conversation_id):
                    with lending_session(user_id=user_id, conversation_id=conversation_id):
                        with staking_session(user_id=user_id, conversation_id=conversation_id):
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
