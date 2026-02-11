"""
Shared utility functions extracted from the old Supervisor class.

All functions are pure (no class state) and operate on plain data.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from src.agents.metadata import metadata
from src.agents.crypto_data.config import Config as CryptoConfig
from src.agents.swap.config import SwapConfig
from src.agents.lending.config import LendingConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Handoff / delegation detection and sanitisation
# ---------------------------------------------------------------------------

_HANDOFF_KEYWORDS = [
    # Backward delegation (agent -> supervisor)
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
    # Forward delegation (supervisor -> agent)
    "transferred your request",
    "transferring your request",
    "i've transferred",
    "i have transferred",
    "routing your request",
    "delegating to",
    "delegating your",
    "let me route this",
    "let me transfer",
    "let me delegate",
    "i'll delegate",
    "i will delegate",
    "i'll transfer",
    "i will transfer",
    "i'll route",
    "i will route",
    "who can provide",
    "agent will handle",
    "agent will provide",
    "agent who can",
]

_SANITIZE_PHRASES = [
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

_FORWARD_PATTERNS = [
    re.compile(
        r"i[''']ve transferred your request to (?:a |the )?(?:specialized )?[\w\s]+ (?:agent|who)[\w\s,]*\.",
        re.IGNORECASE,
    ),
    re.compile(
        r"i have transferred your request to (?:a |the )?(?:specialized )?[\w\s]+ (?:agent|who)[\w\s,]*\.",
        re.IGNORECASE,
    ),
    re.compile(
        r"let me (?:route|transfer|delegate) (?:this|your request) to [\w\s]+\.",
        re.IGNORECASE,
    ),
    re.compile(
        r"i[''']ll (?:route|transfer|delegate) (?:this|your request) to [\w\s]+\.",
        re.IGNORECASE,
    ),
]


def is_handoff_text(text: str) -> bool:
    """Return True if *text* looks like a delegation/handoff message."""
    if not text:
        return False
    t = text.strip().lower()
    return any(k in t for k in _HANDOFF_KEYWORDS)


def sanitize_handoff_phrases(text: str) -> str:
    """Strip delegation phrases from *text*."""
    if not text:
        return text
    sanitized = text
    for p in _SANITIZE_PHRASES:
        pattern = re.compile(r"\b" + re.escape(p) + r"\b[\s\.,;:!\)]*", re.IGNORECASE)
        sanitized = pattern.sub(" ", sanitized)
    for pat in _FORWARD_PATTERNS:
        sanitized = pat.sub(" ", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized


# ---------------------------------------------------------------------------
# Message content extraction
# ---------------------------------------------------------------------------

def get_text_content(message: Any) -> Optional[str]:
    """Extract plain text from a LangChain message (str or list content)."""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        collected: List[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if isinstance(text, str) and text.strip():
                    collected.append(text.strip())
            else:
                text_attr = getattr(part, "text", None)
                if isinstance(text_attr, str) and text_attr.strip():
                    collected.append(text_attr.strip())
        if collected:
            return " ".join(collected)
    return None


# ---------------------------------------------------------------------------
# Response extraction from agent graph output
# ---------------------------------------------------------------------------

KNOWN_AGENT_NAMES = {
    "crypto_agent",
    "database_agent",
    "swap_agent",
    "dca_agent",
    "lending_agent",
    "staking_agent",
    "search_agent",
    "default_agent",
}


def extract_response_from_graph(response: Any) -> Tuple[str, str, list]:
    """
    Parse agent output and return (agent_name, cleaned_text, messages_out).
    """
    messages_out = response.get("messages", []) if isinstance(response, dict) else []
    final_response = None
    final_agent = "supervisor"

    def _choose(m):
        content_text = get_text_content(m)
        if not content_text:
            return None, None
        sanitized = sanitize_handoff_phrases(content_text)
        if sanitized and sanitized.strip() and not is_handoff_text(sanitized):
            return sanitized, getattr(m, "name", None)
        return None, None

    # 1) Last message from a known agent
    for m in reversed(messages_out):
        agent_name = getattr(m, "name", None)
        if agent_name in KNOWN_AGENT_NAMES:
            content, agent = _choose(m)
            if content:
                final_response = content
                final_agent = agent or agent_name
                break

    # 2) Fallback: any last message with content
    if final_response is None:
        for m in reversed(messages_out):
            content, agent = _choose(m)
            if content:
                final_response = content
                if agent:
                    final_agent = agent
                break

    # 3) Last resort
    if final_response is None:
        if isinstance(response, dict):
            final_response = response.get("response") or "No response available"
            final_agent = response.get("agent", final_agent)
        else:
            final_response = "No response available"

    cleaned_response = final_response or "Sorry, no meaningful response was returned."
    final_agent = final_agent or "supervisor"
    return final_agent, cleaned_response, messages_out


# ---------------------------------------------------------------------------
# Metadata building
# ---------------------------------------------------------------------------

def build_metadata(
    agent_name: str,
    user_id: Optional[str],
    conversation_id: Optional[str],
    messages_out: list,
) -> dict:
    """Build the metadata envelope for a given agent response."""

    def _with_history(meta, get_history_fn):
        if not meta:
            return {}
        meta = meta.copy()
        history = get_history_fn()
        if history:
            meta.setdefault("history", history)
        return meta

    if agent_name == "swap_agent":
        swap_meta = metadata.get_swap_agent(user_id=user_id, conversation_id=conversation_id)
        return _with_history(
            swap_meta,
            lambda: metadata.get_swap_history(user_id=user_id, conversation_id=conversation_id),
        )

    if agent_name == "dca_agent":
        dca_meta = metadata.get_dca_agent(user_id=user_id, conversation_id=conversation_id)
        return _with_history(
            dca_meta,
            lambda: metadata.get_dca_history(user_id=user_id, conversation_id=conversation_id),
        )

    if agent_name == "lending_agent":
        lending_meta = metadata.get_lending_agent(user_id=user_id, conversation_id=conversation_id)
        return _with_history(
            lending_meta,
            lambda: metadata.get_lending_history(user_id=user_id, conversation_id=conversation_id),
        )

    if agent_name == "staking_agent":
        staking_meta = metadata.get_staking_agent(user_id=user_id, conversation_id=conversation_id)
        return _with_history(
            staking_meta,
            lambda: metadata.get_staking_history(user_id=user_id, conversation_id=conversation_id),
        )

    if agent_name == "crypto_agent":
        tool_meta = _collect_tool_metadata(messages_out)
        if tool_meta:
            metadata.set_crypto_data_agent(tool_meta)
        return metadata.get_crypto_data_agent() or {}

    return {}


def _collect_tool_metadata(messages_out: list) -> dict:
    """Extract metadata from tool messages in agent output."""
    for m in reversed(messages_out):
        t = get_text_content(m) or ""
        meta, _ = _extract_payload(t)
        if meta:
            return meta
        art = getattr(m, "artifact", None)
        if isinstance(art, dict) and art:
            return art
    return {}


def _extract_payload(text: str) -> Tuple[dict, str]:
    """Try JSON payload or sentinel-based metadata from text."""
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "metadata" in obj and "text" in obj:
            return (obj.get("metadata") or {}), str(obj.get("text") or "")
    except Exception:
        pass
    m = re.search(r"\|\|META:\s*(\{.*?\})\|\|", text)
    if m:
        try:
            meta = json.loads(m.group(1))
        except Exception:
            meta = {}
        cleaned = (text[: m.start()] + text[m.end() :]).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return meta, cleaned
    return {}, text


# ---------------------------------------------------------------------------
# DeFi guidance builders
# ---------------------------------------------------------------------------

def build_defi_guidance(intent_type: str, defi_state: Optional[dict]) -> Optional[str]:
    """Build system-message guidance for in-progress DeFi flows."""
    if not defi_state:
        return None

    status = defi_state.get("status")
    next_field = defi_state.get("next_field")
    pending_question = defi_state.get("pending_question")

    if intent_type == "dca":
        in_progress_statuses = {"consulting", "recommendation", "confirmation"}
        if status not in in_progress_statuses:
            return None
        parts = [
            "There is an in-progress DCA planning session for this conversation.",
            "Keep routing messages to the dca_agent until the workflow is confirmed or the user cancels.",
        ]
    elif intent_type == "swap":
        if status != "collecting":
            return None
        parts = [
            "There is an in-progress token swap intent for this conversation.",
            "Keep routing messages to the swap_agent until the intent is complete unless the user explicitly cancels or changes topic.",
        ]
    elif intent_type == "lending":
        if status != "collecting":
            return None
        parts = [
            "There is an in-progress lending intent for this conversation.",
            "Keep routing messages to the lending_agent until the intent is complete unless the user explicitly cancels or changes topic.",
        ]
    elif intent_type == "staking":
        if status != "collecting":
            return None
        parts = [
            "There is an in-progress staking intent for this conversation.",
            "Keep routing messages to the staking_agent until the intent is complete unless the user explicitly cancels or changes topic.",
        ]
    else:
        return None

    if status:
        parts.append(f"The current stage is: {status}.")
    if next_field:
        parts.append(f"The next field to collect is: {next_field}.")
    if pending_question:
        parts.append(f"Continue the flow by asking: {pending_question}")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Preflight parameter mapping
# ---------------------------------------------------------------------------

def build_preflight_params(intent: str, extracted) -> dict:
    """Map PreExtractedParams to the dict expected by run_preflight."""
    if intent == "swap":
        return {
            "from_network": extracted.from_network,
            "from_token": extracted.from_token,
            "to_network": extracted.to_network or extracted.from_network,
            "to_token": extracted.to_token,
            "amount": extracted.amount,
        }
    if intent == "lending":
        return {
            "action": extracted.action,
            "network": extracted.from_network,
            "asset": extracted.from_token,
            "amount": extracted.amount,
        }
    if intent == "staking":
        return {
            "action": extracted.action,
            "amount": extracted.amount,
        }
    return {}


# ---------------------------------------------------------------------------
# Pending followup detection
# ---------------------------------------------------------------------------

def detect_pending_followups(messages: List[Any]) -> Tuple[bool, bool]:
    """Check message history for pending swap/DCA followups."""
    awaiting_swap = False
    awaiting_dca = False

    def _get(entry, dict_keys, attr_name):
        if isinstance(entry, dict):
            for key in dict_keys:
                if key in entry:
                    return entry.get(key)
            return None
        return getattr(entry, attr_name, None)

    for entry in reversed(messages):
        role_raw = _get(entry, ("role", "Role"), "role")
        agent_label_raw = _get(entry, ("agent_name", "agentName"), "agent_name")
        action_type_raw = _get(entry, ("action_type", "actionType"), "action_type")
        requires_action_raw = _get(entry, ("requires_action", "requiresAction"), "requires_action")
        metadata_payload = _get(entry, ("metadata",), "metadata") or {}

        role = str(role_raw or "").lower()
        if role != "assistant":
            continue
        agent_label = str(agent_label_raw or "").lower()
        action_type = str(action_type_raw or "").lower()
        requires_action = bool(requires_action_raw)
        status = str(
            (metadata_payload.get("status") if isinstance(metadata_payload, dict) else "") or ""
        ).lower()

        if requires_action and status != "ready":
            if action_type == "swap" or "swap" in agent_label:
                awaiting_swap = True
            if action_type == "dca" or "dca" in agent_label:
                awaiting_dca = True
        break

    return awaiting_swap, awaiting_dca


# ---------------------------------------------------------------------------
# Keyword-based intent detection (fallback)
# ---------------------------------------------------------------------------

def build_swap_detection_terms() -> Tuple[set, set]:
    """Build sets of network/token terms for keyword-based swap detection."""
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


def build_lending_detection_terms() -> Tuple[set, set]:
    """Build sets of network/asset terms for keyword-based lending detection."""
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


def is_swap_like_request(
    messages: List[Dict[str, Any]],
    network_terms: set,
    token_terms: set,
) -> bool:
    """Check if the latest user message looks like a swap request."""
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        lowered = content.lower()
        swap_keywords = ("swap", "swapping", "exchange", "convert", "trade")
        if not any(keyword in lowered for keyword in swap_keywords):
            return False
        if any(term and term in lowered for term in network_terms):
            return True
        if any(term and term in lowered for term in token_terms):
            return True
        if "token" in lowered or any(ch.isdigit() for ch in lowered):
            return True
        return True
    return False


def is_lending_like_request(
    messages: List[Dict[str, Any]],
    network_terms: set,
    asset_terms: set,
) -> bool:
    """Check if the latest user message looks like a lending request."""
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        lowered = content.lower()
        lending_keywords = (
            "lend", "lending", "supply", "borrow", "repay",
            "withdraw", "deposit", "aave", "compound",
        )
        if not any(keyword in lowered for keyword in lending_keywords):
            return False
        if any(term and term in lowered for term in network_terms):
            return True
        if any(term and term in lowered for term in asset_terms):
            return True
        if any(ch.isdigit() for ch in lowered):
            return True
        return True
    return False


def is_staking_like_request(messages: List[Dict[str, Any]]) -> bool:
    """Check if the latest user message looks like a staking request."""
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        lowered = content.lower()
        staking_keywords = (
            "stake", "staking", "unstake", "unstaking",
            "steth", "lido", "liquid staking", "staking rewards", "eth staking",
        )
        if not any(keyword in lowered for keyword in staking_keywords):
            return False
        return True
    return False
