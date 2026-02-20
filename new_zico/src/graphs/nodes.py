"""
All graph node functions for the StateGraph pipeline.

Each node takes an AgentState dict and returns a partial state update.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from src.agents.config import Config
from src.agents.metadata import metadata
from src.agents.mode_directives import get_generic_directive, get_agent_directive
from src.agents.routing.semantic_router import SemanticRouter
from src.agents.routing.pre_extractor import pre_extract
from src.agents.memory.windowing import prepare_context
from src.agents.validation.preflight import run_preflight

from src.graphs.state import AgentState
from src.graphs.utils import (
    build_defi_guidance,
    build_metadata,
    build_preflight_params,
    build_swap_detection_terms,
    build_lending_detection_terms,
    detect_pending_followups,
    extract_response_from_graph,
    get_text_content,
    is_swap_like_request,
)

# --- Agent imports ---
from src.agents.crypto_data.agent import CryptoDataAgent
from src.agents.database.agent import DatabaseAgent
from src.agents.default.agent import DefaultAgent
from src.agents.swap.agent import SwapAgent
from src.agents.swap.tools import swap_session
from src.agents.swap.prompt import SWAP_AGENT_SYSTEM_PROMPT
from src.agents.dca.agent import DcaAgent
from src.agents.dca.tools import dca_session
from src.agents.dca.prompt import DCA_AGENT_SYSTEM_PROMPT
from src.agents.lending.agent import LendingAgent
from src.agents.lending.tools import lending_session
from src.agents.lending.prompt import LENDING_AGENT_SYSTEM_PROMPT
from src.agents.staking.agent import StakingAgent
from src.agents.staking.tools import staking_session
from src.agents.staking.prompt import STAKING_AGENT_SYSTEM_PROMPT
from src.agents.search.agent import SearchAgent
from src.agents.portfolio.agent import PortfolioAdvisorAgent
from src.agents.portfolio.tools import portfolio_session
from src.agents.portfolio.prompt import PORTFOLIO_ADVISOR_SYSTEM_PROMPT
from src.agents.database.client import is_database_available

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level singletons (initialised once at startup)
# ---------------------------------------------------------------------------

_agents: Dict[str, Any] = {}
_reasoning_agents: Dict[str, Any] = {}  # Lazy-built reasoning-tier agents
_semantic_router: Optional[SemanticRouter] = None
_swap_network_terms: set = set()
_swap_token_terms: set = set()
_lending_network_terms: set = set()
_lending_asset_terms: set = set()

# Maps agent keys to their builder classes for lazy reasoning agent creation
_AGENT_BUILDERS: Dict[str, type] = {}


def _get_agent(agent_key: str, mode: str = "fast"):
    """Return the agent runnable for the given key and response mode.

    Fast mode returns the startup-initialised singleton.
    Reasoning mode lazily creates and caches an agent built with the
    reasoning-tier LLM (gemini-3-flash-preview).
    """
    if mode != "reasoning":
        return _agents.get(agent_key)

    if agent_key in _reasoning_agents:
        return _reasoning_agents[agent_key]

    builder_cls = _AGENT_BUILDERS.get(agent_key)
    if not builder_cls:
        # No builder registered — fall back to the fast agent
        logger.warning("No reasoning builder for %s; using fast agent", agent_key)
        return _agents.get(agent_key)

    reasoning_llm = Config.get_reasoning_llm(with_cost_tracking=True)
    agent_instance = builder_cls(reasoning_llm)
    _reasoning_agents[agent_key] = agent_instance.agent
    logger.info("Lazily built reasoning agent for %s", agent_key)
    return _reasoning_agents[agent_key]


def initialize_agents() -> None:
    """Build all agent instances and the semantic router. Call once at startup."""
    global _agents, _semantic_router, _AGENT_BUILDERS
    global _swap_network_terms, _swap_token_terms
    global _lending_network_terms, _lending_asset_terms

    llm = Config.get_fast_llm(with_cost_tracking=True)
    embeddings = Config.get_embeddings()

    # Semantic router
    _semantic_router = SemanticRouter(embeddings)
    try:
        _semantic_router.warm_up()
    except Exception:
        logger.warning("SemanticRouter warm-up failed; keyword fallback will be used.")

    # Build fast-tier agents (gemini-2.5-flash)
    _agents["crypto_agent"] = CryptoDataAgent(llm).agent
    _agents["search_agent"] = SearchAgent(llm).agent
    _agents["default_agent"] = DefaultAgent(llm).agent
    _agents["swap_agent"] = SwapAgent(llm).agent
    _agents["dca_agent"] = DcaAgent(llm).agent
    _agents["lending_agent"] = LendingAgent(llm).agent
    _agents["staking_agent"] = StakingAgent(llm).agent

    _agents["portfolio_advisor"] = PortfolioAdvisorAgent(llm).agent

    if is_database_available():
        _agents["database_agent"] = DatabaseAgent(llm)
    else:
        logger.info("Database not available; database_agent disabled.")

    # Register builder classes for lazy reasoning-tier agent creation
    _AGENT_BUILDERS = {
        "crypto_agent": CryptoDataAgent,
        "search_agent": SearchAgent,
        "default_agent": DefaultAgent,
        "swap_agent": SwapAgent,
        "dca_agent": DcaAgent,
        "lending_agent": LendingAgent,
        "staking_agent": StakingAgent,
        "portfolio_advisor": PortfolioAdvisorAgent,
    }

    # Keyword detection terms
    _swap_network_terms, _swap_token_terms = build_swap_detection_terms()
    _lending_network_terms, _lending_asset_terms = build_lending_detection_terms()

    logger.info("All agents initialised: %s", list(_agents.keys()))


# ---------------------------------------------------------------------------
# Node: entry_node — zero LLM calls
# ---------------------------------------------------------------------------

def entry_node(state: AgentState) -> dict:
    """Windowing, DeFi state lookup, message building. Zero LLM calls."""
    messages = state.get("messages", [])
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")

    # Conversation windowing
    fast_llm = Config.get_fast_llm(with_cost_tracking=True)
    windowed = prepare_context(messages, max_recent=8, summarizer_llm=fast_llm)

    # Detect pending followups
    awaiting_swap, awaiting_dca = detect_pending_followups(messages)

    # Build LangChain messages
    langchain_messages: List[Any] = []
    for msg in windowed:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            langchain_messages.append(HumanMessage(content=content))
        elif role == "system":
            langchain_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))

    today = date.today().strftime("%B %d, %Y")
    response_mode = state.get("response_mode", "fast")
    mode_directive = get_generic_directive(response_mode)
    base_instructions = (
        f"Today's date is {today}.\n"
        "Always respond in English, regardless of the user's language."
    )
    if mode_directive:
        base_instructions += f"\n\n{mode_directive}"
    langchain_messages.insert(
        0,
        SystemMessage(content=base_instructions),
    )

    # Existing DeFi states
    dca_state = metadata.get_dca_agent(user_id=user_id, conversation_id=conversation_id)
    swap_state = metadata.get_swap_agent(user_id=user_id, conversation_id=conversation_id)
    lending_state = metadata.get_lending_agent(user_id=user_id, conversation_id=conversation_id)
    staking_state = metadata.get_staking_agent(user_id=user_id, conversation_id=conversation_id)

    # Last user message
    last_user_msg = ""
    for msg in reversed(windowed):
        if msg.get("role") == "user":
            last_user_msg = (msg.get("content") or "").strip()
            break

    # Active DeFi flow?
    has_active_defi = any(
        s and s.get("status") in ("collecting", "consulting", "recommendation", "confirmation")
        for s in (swap_state, lending_state, staking_state, dca_state)
    )

    return {
        "windowed_messages": windowed,
        "langchain_messages": langchain_messages,
        "last_user_message": last_user_msg,
        "swap_state": swap_state or None,
        "lending_state": lending_state or None,
        "staking_state": staking_state or None,
        "dca_state": dca_state or None,
        "awaiting_swap": awaiting_swap,
        "awaiting_dca": awaiting_dca,
        "has_active_defi": has_active_defi,
        "preflight_errors": [],
        "nodes_executed": ["entry_node"],
    }


# ---------------------------------------------------------------------------
# Node: semantic_router_node — embedding classification + pre-extraction
# ---------------------------------------------------------------------------

def semantic_router_node(state: AgentState) -> dict:
    """Classify intent via embeddings, pre-extract params, run preflight.

    If ``route_intent`` is already populated (e.g. pre-classified from the
    audio transcription step), the embedding classification is skipped —
    saving ~200 ms.  Pre-extraction and preflight still run normally.
    """
    last_user_msg = state.get("last_user_message", "")
    has_active_defi = state.get("has_active_defi", False)
    nodes = list(state.get("nodes_executed", []))
    nodes.append("semantic_router_node")

    # --- Check for pre-classified intent (audio path) ---
    pre_intent = state.get("route_intent")
    pre_confidence = state.get("route_confidence", 0.0)
    pre_agent = state.get("route_agent")

    if pre_intent and pre_confidence > 0:
        # Already classified (e.g. audio transcription + classification)
        logger.debug(
            "SemanticRouter SKIPPED (pre-classified): intent=%s confidence=%.3f agent=%s",
            pre_intent, pre_confidence, pre_agent,
        )
        intent_str = pre_intent
        confidence = pre_confidence
        agent_name = pre_agent
        needs_confirm = confidence < SemanticRouter.HIGH_CONFIDENCE
    else:
        # Normal path: classify via embeddings
        route = None
        if last_user_msg and not has_active_defi and _semantic_router:
            route = _semantic_router.classify(last_user_msg)
            if route:
                logger.debug(
                    "SemanticRouter: intent=%s confidence=%.3f agent=%s",
                    route.intent.value,
                    route.confidence,
                    route.agent_name,
                )

        intent_str = route.intent.value if route else None
        confidence = route.confidence if route else 0.0
        agent_name = route.agent_name if route else None
        needs_confirm = route.needs_llm_confirmation if route else True

    # Pre-extraction + preflight (runs regardless of classification source)
    extracted = None
    preflight_errors: List[str] = []
    pre_hint: Optional[str] = None

    if intent_str and confidence >= SemanticRouter.LOW_CONFIDENCE:
        if intent_str in ("swap", "lending", "staking", "dca"):
            extracted = pre_extract(last_user_msg, intent_str)

            # Preflight validation
            if extracted and extracted.has_any() and intent_str in ("swap", "lending", "staking"):
                preflight_params = build_preflight_params(intent_str, extracted)
                preflight_errors = run_preflight(intent_str, preflight_params)

            # Parameter hint for downstream agent
            if not preflight_errors and extracted and extracted.has_any():
                pre_hint = extracted.to_hint()

    return {
        "route_intent": intent_str,
        "route_confidence": confidence,
        "route_agent": agent_name,
        "needs_llm_confirmation": needs_confirm,
        "preflight_errors": preflight_errors,
        "pre_extracted_hint": pre_hint,
        "nodes_executed": nodes,
    }


# ---------------------------------------------------------------------------
# Node: llm_router_node — 1 LLM call for disambiguation
# ---------------------------------------------------------------------------

_LLM_ROUTER_PROMPT = """You are a routing assistant. Given the user's message, determine which agent should handle it.

Available agents:
- crypto_agent: Cryptocurrency prices, market data, NFT floor prices, DeFi TVL.
- swap_agent: Token swap operations.
- dca_agent: Dollar-cost averaging strategies.
- lending_agent: Lending operations (supply, borrow, repay, withdraw).
- staking_agent: Staking operations (stake ETH, unstake stETH via Lido).
- portfolio_advisor: Portfolio analysis, risk assessment, wallet holdings, rebalancing advice.
- search_agent: Web search for current events and factual lookups.
- database_agent: Database queries and data analysis.
- default_agent: General conversation, education, greetings.

Respond with ONLY the agent name (e.g. "crypto_agent"). Nothing else."""


def llm_router_node(state: AgentState) -> dict:
    """Use a single LLM call to disambiguate low-confidence intents."""
    last_msg = state.get("last_user_message", "")
    nodes = list(state.get("nodes_executed", []))
    nodes.append("llm_router_node")

    llm = Config.get_fast_llm(with_cost_tracking=True)

    try:
        response = llm.invoke([
            SystemMessage(content=_LLM_ROUTER_PROMPT),
            HumanMessage(content=last_msg),
        ])
        raw = get_text_content(response) or "default_agent"
        chosen = raw.strip().lower().replace(" ", "_")

        # Validate
        valid_agents = {
            "crypto_agent", "swap_agent", "dca_agent", "lending_agent",
            "staking_agent", "portfolio_advisor", "search_agent",
            "database_agent", "default_agent",
        }
        if chosen not in valid_agents:
            chosen = "default_agent"

    except Exception:
        logger.exception("LLM router failed; defaulting to default_agent.")
        chosen = "default_agent"

    return {
        "route_agent": chosen,
        "route_confidence": 1.0,
        "needs_llm_confirmation": False,
        "nodes_executed": nodes,
    }


# ---------------------------------------------------------------------------
# Node: error_node — return preflight errors (0 LLM calls)
# ---------------------------------------------------------------------------

def error_node(state: AgentState) -> dict:
    """Return preflight validation errors directly."""
    errors = state.get("preflight_errors", [])
    nodes = list(state.get("nodes_executed", []))
    nodes.append("error_node")

    friendly = "; ".join(errors)
    return {
        "final_response": f"I can't proceed with that request: {friendly}. Please correct the details and try again.",
        "response_agent": "supervisor",
        "response_metadata": {},
        "raw_agent_messages": [],
        "nodes_executed": nodes,
    }


# ---------------------------------------------------------------------------
# Agent wrapper nodes
# ---------------------------------------------------------------------------

def _invoke_defi_agent(
    agent_key: str,
    system_prompt: str,
    session_ctx,
    state: AgentState,
    intent_type: str,
    config: RunnableConfig | None = None,
) -> dict:
    """Shared logic for invoking a DeFi agent with session scoping."""
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")
    response_mode = state.get("response_mode", "fast")
    langchain_messages = list(state.get("langchain_messages", []))
    nodes = list(state.get("nodes_executed", []))
    nodes.append(f"{agent_key}_node")

    agent = _get_agent(agent_key, response_mode)
    if not agent:
        return {
            "final_response": "Agent not available.",
            "response_agent": agent_key,
            "response_metadata": {},
            "raw_agent_messages": [],
            "nodes_executed": nodes,
        }

    # Inject system prompt
    scoped_messages = [SystemMessage(content=system_prompt)]

    # Inject per-agent mode directive
    agent_directive = get_agent_directive(agent_key, response_mode)
    if agent_directive:
        scoped_messages.append(SystemMessage(content=agent_directive))

    # Inject DeFi guidance if in-progress
    defi_state = state.get(f"{intent_type}_state")
    guidance = build_defi_guidance(intent_type, defi_state)
    if guidance:
        scoped_messages.append(SystemMessage(content=guidance))

    # Inject pre-extracted hint
    hint = state.get("pre_extracted_hint")
    if hint:
        scoped_messages.append(SystemMessage(content=hint))

    scoped_messages.extend(langchain_messages)

    try:
        with session_ctx(user_id=user_id, conversation_id=conversation_id):
            response = agent.invoke({"messages": scoped_messages}, config=config)
    except Exception:
        logger.exception("Error invoking %s", agent_key)
        return {
            "final_response": "Sorry, an error occurred while processing your request.",
            "response_agent": agent_key,
            "response_metadata": {},
            "raw_agent_messages": [],
            "nodes_executed": nodes,
        }

    agent_name, text, messages_out = extract_response_from_graph(response)
    meta = build_metadata(agent_name or agent_key, user_id, conversation_id, messages_out)

    return {
        "final_response": text,
        "response_agent": agent_name or agent_key,
        "response_metadata": meta,
        "raw_agent_messages": messages_out,
        "nodes_executed": nodes,
    }


def swap_agent_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """Invoke swap agent with both swap and portfolio session contexts.

    The portfolio session gives the swap agent access to ``get_user_portfolio``
    so users can check balances mid-swap without leaving the flow.
    """
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")
    wallet_address = state.get("wallet_address")
    response_mode = state.get("response_mode", "fast")
    langchain_messages = list(state.get("langchain_messages", []))
    nodes = list(state.get("nodes_executed", []))
    nodes.append("swap_agent_node")

    agent = _get_agent("swap_agent", response_mode)
    if not agent:
        return {
            "final_response": "Agent not available.",
            "response_agent": "swap_agent",
            "response_metadata": {},
            "raw_agent_messages": [],
            "nodes_executed": nodes,
        }

    # Inject system prompt + per-agent mode directive + DeFi guidance
    scoped_messages = [SystemMessage(content=SWAP_AGENT_SYSTEM_PROMPT)]

    agent_directive = get_agent_directive("swap_agent", response_mode)
    if agent_directive:
        scoped_messages.append(SystemMessage(content=agent_directive))

    defi_state = state.get("swap_state")
    guidance = build_defi_guidance("swap", defi_state)
    if guidance:
        scoped_messages.append(SystemMessage(content=guidance))

    hint = state.get("pre_extracted_hint")
    if hint:
        scoped_messages.append(SystemMessage(content=hint))

    scoped_messages.extend(langchain_messages)

    try:
        with swap_session(user_id=user_id, conversation_id=conversation_id):
            with portfolio_session(user_id=user_id, conversation_id=conversation_id, wallet_address=wallet_address):
                response = agent.invoke({"messages": scoped_messages}, config=config)
    except Exception:
        logger.exception("Error invoking swap_agent")
        return {
            "final_response": "Sorry, an error occurred while processing your request.",
            "response_agent": "swap_agent",
            "response_metadata": {},
            "raw_agent_messages": [],
            "nodes_executed": nodes,
        }

    agent_name, text, messages_out = extract_response_from_graph(response)
    meta = build_metadata(agent_name or "swap_agent", user_id, conversation_id, messages_out)

    return {
        "final_response": text,
        "response_agent": agent_name or "swap_agent",
        "response_metadata": meta,
        "raw_agent_messages": messages_out,
        "nodes_executed": nodes,
    }


def lending_agent_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    return _invoke_defi_agent("lending_agent", LENDING_AGENT_SYSTEM_PROMPT, lending_session, state, "lending", config)


def staking_agent_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    return _invoke_defi_agent("staking_agent", STAKING_AGENT_SYSTEM_PROMPT, staking_session, state, "staking", config)


def dca_agent_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    return _invoke_defi_agent("dca_agent", DCA_AGENT_SYSTEM_PROMPT, dca_session, state, "dca", config)


def _invoke_simple_agent(agent_key: str, state: AgentState, config: RunnableConfig | None = None) -> dict:
    """Shared logic for invoking a non-DeFi agent (no session scoping)."""
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")
    response_mode = state.get("response_mode", "fast")
    langchain_messages = list(state.get("langchain_messages", []))
    nodes = list(state.get("nodes_executed", []))
    nodes.append(f"{agent_key}_node")

    agent = _get_agent(agent_key, response_mode)
    if not agent:
        return {
            "final_response": "Agent not available.",
            "response_agent": agent_key,
            "response_metadata": {},
            "raw_agent_messages": [],
            "nodes_executed": nodes,
        }

    # Inject per-agent mode directive if available
    agent_directive = get_agent_directive(agent_key, response_mode)
    if agent_directive:
        invoke_messages = [SystemMessage(content=agent_directive)] + langchain_messages
    else:
        invoke_messages = langchain_messages

    try:
        response = agent.invoke({"messages": invoke_messages}, config=config)
    except Exception:
        logger.exception("Error invoking %s", agent_key)
        return {
            "final_response": "Sorry, an error occurred while processing your request.",
            "response_agent": agent_key,
            "response_metadata": {},
            "raw_agent_messages": [],
            "nodes_executed": nodes,
        }

    agent_name, text, messages_out = extract_response_from_graph(response)
    meta = build_metadata(agent_name or agent_key, user_id, conversation_id, messages_out)

    return {
        "final_response": text,
        "response_agent": agent_name or agent_key,
        "response_metadata": meta,
        "raw_agent_messages": messages_out,
        "nodes_executed": nodes,
    }


def crypto_agent_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    return _invoke_simple_agent("crypto_agent", state, config)


def search_agent_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    return _invoke_simple_agent("search_agent", state, config)


def default_agent_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    return _invoke_simple_agent("default_agent", state, config)


def portfolio_advisor_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """Invoke the portfolio advisor with wallet_address session context."""
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")
    wallet_address = state.get("wallet_address")
    response_mode = state.get("response_mode", "fast")
    langchain_messages = list(state.get("langchain_messages", []))
    nodes = list(state.get("nodes_executed", []))
    nodes.append("portfolio_advisor_node")

    agent = _get_agent("portfolio_advisor", response_mode)
    if not agent:
        return {
            "final_response": "Portfolio advisor is not available.",
            "response_agent": "portfolio_advisor",
            "response_metadata": {},
            "raw_agent_messages": [],
            "nodes_executed": nodes,
        }

    # Inject system prompt + per-agent mode directive
    scoped_messages = [SystemMessage(content=PORTFOLIO_ADVISOR_SYSTEM_PROMPT)]

    agent_directive = get_agent_directive("portfolio_advisor", response_mode)
    if agent_directive:
        scoped_messages.append(SystemMessage(content=agent_directive))

    scoped_messages.extend(langchain_messages)

    try:
        with portfolio_session(user_id=user_id, conversation_id=conversation_id, wallet_address=wallet_address):
            response = agent.invoke({"messages": scoped_messages}, config=config)
    except Exception:
        logger.exception("Error invoking portfolio_advisor")
        return {
            "final_response": "Sorry, an error occurred while analyzing your portfolio.",
            "response_agent": "portfolio_advisor",
            "response_metadata": {},
            "raw_agent_messages": [],
            "nodes_executed": nodes,
        }

    agent_name, text, messages_out = extract_response_from_graph(response)
    meta = build_metadata(agent_name or "portfolio_advisor", user_id, conversation_id, messages_out)

    return {
        "final_response": text,
        "response_agent": agent_name or "portfolio_advisor",
        "response_metadata": meta,
        "raw_agent_messages": messages_out,
        "nodes_executed": nodes,
    }


def database_agent_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    return _invoke_simple_agent("database_agent", state, config)
