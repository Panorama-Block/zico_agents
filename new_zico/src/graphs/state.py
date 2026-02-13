"""
Centralized AgentState for the StateGraph pipeline.

Every node reads from and writes to this shared state dict.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # --- Input ---
    messages: List[Dict[str, Any]]          # Raw conversation messages from the gateway
    user_id: str
    conversation_id: str
    wallet_address: Optional[str]           # EVM wallet address (from HTTP request)

    # --- Windowed context ---
    windowed_messages: List[Dict[str, Any]] # After context windowing
    langchain_messages: List[Any]           # LangChain message objects

    # --- Routing ---
    last_user_message: str
    route_intent: Optional[str]             # IntentCategory value
    route_confidence: float
    route_agent: Optional[str]              # Target agent name
    needs_llm_confirmation: bool
    has_active_defi: bool                   # In-progress DeFi flow detected

    # --- Pre-processing ---
    pre_extracted_hint: Optional[str]       # Pre-extracted parameter hint
    preflight_errors: List[str]             # Validation errors (empty = valid)

    # --- DeFi state ---
    swap_state: Optional[Dict[str, Any]]
    lending_state: Optional[Dict[str, Any]]
    staking_state: Optional[Dict[str, Any]]
    dca_state: Optional[Dict[str, Any]]
    awaiting_swap: bool
    awaiting_dca: bool

    # --- Output ---
    final_response: str
    response_agent: str
    response_metadata: Dict[str, Any]
    raw_agent_messages: List[Any]           # Raw messages from agent invocation

    # --- Observability ---
    nodes_executed: List[str]               # Trace of executed node names
