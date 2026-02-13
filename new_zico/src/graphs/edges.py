"""
Conditional edge functions for the StateGraph.

These are pure functions that inspect the AgentState and return
the name of the next node to execute.
"""

from __future__ import annotations

import logging

from src.agents.routing.semantic_router import IntentCategory, SemanticRouter
from src.graphs.state import AgentState
from src.graphs import nodes as _nodes_mod
from src.graphs.utils import (
    is_swap_like_request,
    is_lending_like_request,
    is_staking_like_request,
)

logger = logging.getLogger(__name__)

# Agent name → node name mapping
_INTENT_TO_NODE = {
    IntentCategory.SWAP.value: "swap_agent_node",
    IntentCategory.LENDING.value: "lending_agent_node",
    IntentCategory.STAKING.value: "staking_agent_node",
    IntentCategory.DCA.value: "dca_agent_node",
    IntentCategory.MARKET_DATA.value: "crypto_agent_node",
    IntentCategory.PORTFOLIO.value: "portfolio_advisor_node",
    IntentCategory.SEARCH.value: "search_agent_node",
    IntentCategory.EDUCATION.value: "default_agent_node",
    IntentCategory.GENERAL.value: "default_agent_node",
}

_AGENT_NAME_TO_NODE = {
    "swap_agent": "swap_agent_node",
    "lending_agent": "lending_agent_node",
    "staking_agent": "staking_agent_node",
    "dca_agent": "dca_agent_node",
    "crypto_agent": "crypto_agent_node",
    "search_agent": "search_agent_node",
    "default_agent": "default_agent_node",
    "database_agent": "database_agent_node",
    "portfolio_advisor": "portfolio_advisor_node",
}

# DeFi state key → node mapping
_DEFI_STATE_NODE = {
    "swap_state": "swap_agent_node",
    "lending_state": "lending_agent_node",
    "staking_state": "staking_agent_node",
    "dca_state": "dca_agent_node",
}

# DeFi in-progress statuses
_DEFI_ACTIVE_STATUSES = {
    "swap_state": {"collecting"},
    "lending_state": {"collecting"},
    "staking_state": {"collecting"},
    "dca_state": {"consulting", "recommendation", "confirmation"},
}


def decide_route(state: AgentState) -> str:
    """
    Main routing decision after semantic_router_node.

    Priority order:
    1. Preflight errors → error_node
    2. Active DeFi flow → matching agent node
    3. Awaiting swap/DCA followup → matching agent node
    4. High confidence (>= 0.78) → direct to agent node
    5. DeFi intent + medium confidence (>= 0.50) + keyword match → DeFi agent node
    6. Non-DeFi + medium confidence (>= 0.50) → direct to agent node
    7. Else → llm_router_node
    """
    # 1. Preflight errors
    if state.get("preflight_errors"):
        logger.debug("decide_route → error_node (preflight errors)")
        return "error_node"

    intent = state.get("route_intent")
    confidence = state.get("route_confidence", 0.0)
    windowed = state.get("windowed_messages", [])

    # 2. Active DeFi flow — route based on state
    for state_key, node_name in _DEFI_STATE_NODE.items():
        defi_state = state.get(state_key)
        if defi_state:
            active_statuses = _DEFI_ACTIVE_STATUSES.get(state_key, set())
            if defi_state.get("status") in active_statuses:
                logger.debug("decide_route → %s (active DeFi flow)", node_name)
                return node_name

    # 3. Awaiting followup
    if state.get("awaiting_swap"):
        logger.debug("decide_route → swap_agent_node (awaiting swap)")
        return "swap_agent_node"
    if state.get("awaiting_dca"):
        logger.debug("decide_route → dca_agent_node (awaiting DCA)")
        return "dca_agent_node"

    # 4. High confidence direct routing
    if confidence >= SemanticRouter.HIGH_CONFIDENCE and intent:
        node = _INTENT_TO_NODE.get(intent, "default_agent_node")
        logger.debug("decide_route → %s (high confidence %.3f)", node, confidence)
        return node

    # 5. DeFi intent + medium confidence + keyword match
    if confidence >= SemanticRouter.LOW_CONFIDENCE and intent in ("swap", "lending", "staking", "dca"):
        # For DeFi, medium confidence + keyword fallback is sufficient
        if intent == "swap":
            if _nodes_mod.is_swap_like_request(
                windowed, _nodes_mod._swap_network_terms, _nodes_mod._swap_token_terms
            ):
                logger.debug("decide_route → swap_agent_node (medium confidence + keyword)")
                return "swap_agent_node"
            # Even without keyword match, semantic router says swap
            logger.debug("decide_route → swap_agent_node (medium confidence semantic)")
            return "swap_agent_node"
        if intent == "lending":
            logger.debug("decide_route → lending_agent_node (medium confidence)")
            return "lending_agent_node"
        if intent == "staking":
            logger.debug("decide_route → staking_agent_node (medium confidence)")
            return "staking_agent_node"
        if intent == "dca":
            logger.debug("decide_route → dca_agent_node (medium confidence)")
            return "dca_agent_node"

    # 6. Non-DeFi + medium confidence
    if confidence >= SemanticRouter.LOW_CONFIDENCE and intent:
        node = _INTENT_TO_NODE.get(intent, "default_agent_node")
        logger.debug("decide_route → %s (medium confidence %.3f)", node, confidence)
        return node

    # 7. Keyword-only fallback (no semantic match)
    if is_swap_like_request(
        windowed, _nodes_mod._swap_network_terms, _nodes_mod._swap_token_terms
    ):
        logger.debug("decide_route → swap_agent_node (keyword-only)")
        return "swap_agent_node"
    if is_lending_like_request(
        windowed, _nodes_mod._lending_network_terms, _nodes_mod._lending_asset_terms
    ):
        logger.debug("decide_route → lending_agent_node (keyword-only)")
        return "lending_agent_node"
    if is_staking_like_request(windowed):
        logger.debug("decide_route → staking_agent_node (keyword-only)")
        return "staking_agent_node"

    # 8. Low confidence → LLM router
    logger.debug("decide_route → llm_router_node (low confidence %.3f)", confidence)
    return "llm_router_node"


def after_llm_router(state: AgentState) -> str:
    """Route after LLM refinement — route_agent has been set by llm_router_node."""
    agent = state.get("route_agent", "default_agent")
    node = _AGENT_NAME_TO_NODE.get(agent, "default_agent_node")
    logger.debug("after_llm_router → %s (agent=%s)", node, agent)
    return node
