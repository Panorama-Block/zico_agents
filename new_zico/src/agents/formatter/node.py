"""
Formatter node — converts agent responses to clean markdown.

Smart passthrough: skips the LLM call if the response is already
well-formatted or very short.
"""

from __future__ import annotations

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.config import Config
from src.agents.formatter.prompt import FORMATTER_SYSTEM_PROMPT
from src.graphs.state import AgentState
from src.graphs.utils import sanitize_handoff_phrases

logger = logging.getLogger(__name__)

# Maximum length for "short" responses that skip formatting
_SHORT_RESPONSE_THRESHOLD = 120

# Structural quality: headers/lists MUST be at the start of a line
_STRUCTURAL_MARKERS = re.compile(
    r"(^#{1,3}\s"       # headers at line start
    r"|^\s*[-*]\s"      # bullets at line start
    r"|^\d+\.\s"        # numbered list at line start
    r"|^\|.+\|$"        # table rows
    r")",
    re.MULTILINE,
)


def _already_formatted(text: str) -> bool:
    """Return True if text is properly structured markdown.

    Having **bold** alone is not enough — we need structural elements
    (headers, lists, tables) on their own lines to consider the text
    well-formatted.
    """
    if len(text) <= _SHORT_RESPONSE_THRESHOLD:
        return True
    structural_matches = _STRUCTURAL_MARKERS.findall(text)
    # Need at least 3 structural elements on proper lines
    return len(structural_matches) >= 3


def formatter_node(state: AgentState) -> dict:
    """Format the agent response as clean markdown."""
    response_text = state.get("final_response", "")
    nodes = list(state.get("nodes_executed", []))
    nodes.append("formatter_node")

    # Always sanitize handoff phrases
    response_text = sanitize_handoff_phrases(response_text)

    # Smart passthrough — skip LLM if already formatted or very short
    if not response_text or _already_formatted(response_text):
        return {
            "final_response": response_text,
            "nodes_executed": nodes,
        }

    # Use LLM to format
    try:
        from src.llm.tiers import ModelTier
        llm = Config.get_llm(model=ModelTier.FORMATTER, with_cost_tracking=True)
        result = llm.invoke([
            SystemMessage(content=FORMATTER_SYSTEM_PROMPT),
            HumanMessage(content=response_text),
        ])
        formatted = result.content if isinstance(result.content, str) else response_text
        # Final sanitization
        formatted = sanitize_handoff_phrases(formatted)
    except Exception:
        logger.exception("Formatter LLM call failed; using original response.")
        formatted = response_text

    return {
        "final_response": formatted,
        "nodes_executed": nodes,
    }
