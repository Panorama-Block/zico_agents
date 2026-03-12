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
    is_liquidity_like_request,
)

logger = logging.getLogger(__name__)

# Agent name → node name mapping
_INTENT_TO_NODE = {
    IntentCategory.SWAP.value: "swap_agent_node",
    IntentCategory.LENDING.value: "lending_agent_node",
    IntentCategory.STAKING.value: "staking_agent_node",
    IntentCategory.LIQUIDITY.value: "liquidity_agent_node",
    IntentCategory.DCA.value: "dca_agent_node",
    IntentCategory.STRATEGY.value: "strategy_agent_node",
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
    "liquidity_agent": "liquidity_agent_node",
    "dca_agent": "dca_agent_node",
    "strategy_agent": "strategy_agent_node",
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
    "liquidity_state": "liquidity_agent_node",
    "dca_state": "dca_agent_node",
    "strategy_state": "strategy_agent_node",
}

# DeFi in-progress statuses
_DEFI_ACTIVE_STATUSES = {
    "swap_state": {"collecting"},
    "lending_state": {"collecting"},
    "staking_state": {"collecting"},
    "liquidity_state": {"collecting"},
    "dca_state": {"consulting", "recommendation", "confirmation"},
    "strategy_state": {"profiling", "discovery", "recommendation", "comparison", "confirmation"},
}

_AMBIGUOUS_LIQUIDITY_FOLLOWUPS = {
    "ok",
    "okay",
    "yes",
    "yep",
    "continue",
    "go ahead",
    "go",
    "next",
    "first",
    "first one",
    "the first one",
    "1",
    "1st",
    "max",
    "put max",
    "all",
    "use max",
    "use maximum",
    "full",
}


def _route_with_reason(node: str, reason: str, *, intent: str | None = None, confidence: float | None = None) -> str:
    logger.info(
        "routing.decide node=%s reason=%s intent=%s confidence=%s",
        node,
        reason,
        intent or "none",
        f"{confidence:.3f}" if isinstance(confidence, float) else "n/a",
    )
    return node


def _is_ambiguous_liquidity_followup(message: str) -> bool:
    normalized = " ".join((message or "").strip().lower().split())
    if not normalized:
        return False
    if normalized in _AMBIGUOUS_LIQUIDITY_FOLLOWUPS:
        return True
    if normalized.startswith("max "):
        return True
    return False


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
        return _route_with_reason("error_node", "preflight_errors")

    intent = state.get("route_intent")
    confidence = state.get("route_confidence", 0.0)
    windowed = state.get("windowed_messages", [])

    # 2. Active DeFi flow — route based on state
    for state_key, node_name in _DEFI_STATE_NODE.items():
        defi_state = state.get(state_key)
        if defi_state:
            active_statuses = _DEFI_ACTIVE_STATUSES.get(state_key, set())
            if defi_state.get("status") in active_statuses:
                return _route_with_reason(node_name, f"active_defi:{state_key}", intent=intent, confidence=confidence)

    # 3. Awaiting followup
    if state.get("awaiting_swap"):
        return _route_with_reason("swap_agent_node", "pending_followup:swap", intent=intent, confidence=confidence)
    if state.get("awaiting_dca"):
        return _route_with_reason("dca_agent_node", "pending_followup:dca", intent=intent, confidence=confidence)
    if state.get("awaiting_liquidity"):
        last_user_message = str(state.get("last_user_message") or "")
        if _is_ambiguous_liquidity_followup(last_user_message):
            return _route_with_reason("liquidity_agent_node", "sticky_followup:liquidity", intent=intent, confidence=confidence)

    # 4. High confidence direct routing
    if confidence >= SemanticRouter.HIGH_CONFIDENCE and intent:
        node = _INTENT_TO_NODE.get(intent, "default_agent_node")
        return _route_with_reason(node, "semantic_high_confidence", intent=intent, confidence=confidence)

    # 5. DeFi intent + medium confidence + keyword match
    if confidence >= SemanticRouter.LOW_CONFIDENCE and intent in ("swap", "lending", "staking", "liquidity", "dca", "strategy"):
        # For DeFi, medium confidence + keyword fallback is sufficient
        if intent == "swap":
            if _nodes_mod.is_swap_like_request(
                windowed, _nodes_mod._swap_network_terms, _nodes_mod._swap_token_terms
            ):
                return _route_with_reason("swap_agent_node", "semantic_medium+keyword:swap", intent=intent, confidence=confidence)
            # Even without keyword match, semantic router says swap
            return _route_with_reason("swap_agent_node", "semantic_medium:swap", intent=intent, confidence=confidence)
        if intent == "lending":
            return _route_with_reason("lending_agent_node", "semantic_medium:lending", intent=intent, confidence=confidence)
        if intent == "staking":
            return _route_with_reason("staking_agent_node", "semantic_medium:staking", intent=intent, confidence=confidence)
        if intent == "liquidity":
            return _route_with_reason("liquidity_agent_node", "semantic_medium:liquidity", intent=intent, confidence=confidence)
        if intent == "dca":
            return _route_with_reason("dca_agent_node", "semantic_medium:dca", intent=intent, confidence=confidence)
        if intent == "strategy":
            return _route_with_reason("strategy_agent_node", "semantic_medium:strategy", intent=intent, confidence=confidence)

    # 6. Non-DeFi + medium confidence
    if confidence >= SemanticRouter.LOW_CONFIDENCE and intent:
        node = _INTENT_TO_NODE.get(intent, "default_agent_node")
        return _route_with_reason(node, "semantic_medium_non_defi", intent=intent, confidence=confidence)

    # 7. Keyword-only fallback (no semantic match)
    if is_swap_like_request(
        windowed, _nodes_mod._swap_network_terms, _nodes_mod._swap_token_terms
    ):
        return _route_with_reason("swap_agent_node", "keyword_only:swap", intent=intent, confidence=confidence)
    if is_lending_like_request(
        windowed, _nodes_mod._lending_network_terms, _nodes_mod._lending_asset_terms
    ):
        return _route_with_reason("lending_agent_node", "keyword_only:lending", intent=intent, confidence=confidence)
    if is_staking_like_request(windowed):
        return _route_with_reason("staking_agent_node", "keyword_only:staking", intent=intent, confidence=confidence)
    if is_liquidity_like_request(windowed):
        return _route_with_reason("liquidity_agent_node", "keyword_only:liquidity", intent=intent, confidence=confidence)

    # 8. Low confidence → LLM router
    return _route_with_reason("llm_router_node", "llm_router_low_confidence", intent=intent, confidence=confidence)


def after_llm_router(state: AgentState) -> str:
    """Route after LLM refinement — route_agent has been set by llm_router_node."""
    agent = state.get("route_agent", "default_agent")
    node = _AGENT_NAME_TO_NODE.get(agent, "default_agent_node")
    logger.info("routing.after_llm node=%s reason=llm_router agent=%s", node, agent)
    return node
