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

# Patterns that indicate the response already has markdown formatting
_MARKDOWN_INDICATORS = re.compile(
    r"(\*\*[^*]+\*\*"   # bold
    r"|^#{1,3}\s"        # headers
    r"|^\s*[-*]\s"       # bullets
    r"|^\|.+\|$"         # table rows
    r")",
    re.MULTILINE,
)

# Maximum length for "short" responses that skip formatting
_SHORT_RESPONSE_THRESHOLD = 120


def _already_formatted(text: str) -> bool:
    """Return True if text already contains markdown formatting."""
    if len(text) <= _SHORT_RESPONSE_THRESHOLD:
        return True
    matches = _MARKDOWN_INDICATORS.findall(text)
    return len(matches) >= 2


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
        llm = Config.get_fast_llm(with_cost_tracking=True)
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
