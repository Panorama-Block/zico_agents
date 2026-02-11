"""
StateGraph construction and compilation.

Wires together all nodes and conditional edges into a single compiled graph.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from src.graphs.state import AgentState
from src.graphs.nodes import (
    entry_node,
    semantic_router_node,
    llm_router_node,
    error_node,
    swap_agent_node,
    lending_agent_node,
    staking_agent_node,
    dca_agent_node,
    crypto_agent_node,
    search_agent_node,
    default_agent_node,
    database_agent_node,
)
from src.graphs.edges import decide_route, after_llm_router
from src.agents.formatter.node import formatter_node

logger = logging.getLogger(__name__)

# All agent nodes that feed into the formatter
_AGENT_NODES = [
    "swap_agent_node",
    "lending_agent_node",
    "staking_agent_node",
    "dca_agent_node",
    "crypto_agent_node",
    "search_agent_node",
    "default_agent_node",
    "database_agent_node",
]


def build_graph() -> StateGraph:
    """
    Construct and compile the Zico agent StateGraph.

    Flow:
        entry → semantic_router → {decide_route} → agent / llm_router / error
        llm_router → {after_llm_router} → agent
        agent → formatter → END
        error → END
    """
    graph = StateGraph(AgentState)

    # --- Register nodes ---
    graph.add_node("entry_node", entry_node)
    graph.add_node("semantic_router_node", semantic_router_node)
    graph.add_node("llm_router_node", llm_router_node)
    graph.add_node("error_node", error_node)
    graph.add_node("formatter_node", formatter_node)

    graph.add_node("swap_agent_node", swap_agent_node)
    graph.add_node("lending_agent_node", lending_agent_node)
    graph.add_node("staking_agent_node", staking_agent_node)
    graph.add_node("dca_agent_node", dca_agent_node)
    graph.add_node("crypto_agent_node", crypto_agent_node)
    graph.add_node("search_agent_node", search_agent_node)
    graph.add_node("default_agent_node", default_agent_node)
    graph.add_node("database_agent_node", database_agent_node)

    # --- Entry point ---
    graph.set_entry_point("entry_node")

    # --- Linear edges ---
    graph.add_edge("entry_node", "semantic_router_node")

    # --- Conditional: after semantic router ---
    graph.add_conditional_edges(
        "semantic_router_node",
        decide_route,
        {
            "error_node": "error_node",
            "llm_router_node": "llm_router_node",
            "swap_agent_node": "swap_agent_node",
            "lending_agent_node": "lending_agent_node",
            "staking_agent_node": "staking_agent_node",
            "dca_agent_node": "dca_agent_node",
            "crypto_agent_node": "crypto_agent_node",
            "search_agent_node": "search_agent_node",
            "default_agent_node": "default_agent_node",
            "database_agent_node": "database_agent_node",
        },
    )

    # --- Conditional: after LLM router ---
    graph.add_conditional_edges(
        "llm_router_node",
        after_llm_router,
        {
            "swap_agent_node": "swap_agent_node",
            "lending_agent_node": "lending_agent_node",
            "staking_agent_node": "staking_agent_node",
            "dca_agent_node": "dca_agent_node",
            "crypto_agent_node": "crypto_agent_node",
            "search_agent_node": "search_agent_node",
            "default_agent_node": "default_agent_node",
            "database_agent_node": "database_agent_node",
        },
    )

    # --- All agent nodes → formatter → END ---
    for node_name in _AGENT_NODES:
        graph.add_edge(node_name, "formatter_node")

    graph.add_edge("formatter_node", END)

    # --- Error → END ---
    graph.add_edge("error_node", END)

    compiled = graph.compile()
    logger.info("StateGraph compiled: %d nodes", len(_AGENT_NODES) + 5)
    return compiled
