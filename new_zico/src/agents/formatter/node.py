"""
Formatter node — converts agent responses to clean markdown.

Smart passthrough: skips the LLM call if the response is already
well-formatted or very short.
"""

from __future__ import annotations

import hashlib
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.config import Config
from src.agents.formatter.prompt import FORMATTER_SYSTEM_PROMPT
from src.graphs.state import AgentState
from src.graphs.utils import sanitize_handoff_phrases
from src.diagnostics.response_boundary import update_trace

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


def _is_safe_formatted_output(original: str, formatted: str) -> bool:
    """Return True when formatter output safely preserves substantive content.

    Formatting is presentation-only. A formatter result must never replace a
    meaningful response with empty, malformed, or catastrophically truncated
    output.
    """
    original_clean = original.strip()
    formatted_clean = formatted.strip()

    if not formatted_clean:
        return False

    # A markdown marker without header text is never a valid final response.
    if formatted_clean in {"#", "##", "###"}:
        return False

    # The formatter is instructed to preserve all information. Large content
    # loss therefore indicates a failed or truncated formatter completion.
    if len(original_clean) > _SHORT_RESPONSE_THRESHOLD:
        minimum_safe_length = max(
            _SHORT_RESPONSE_THRESHOLD,
            len(original_clean) // 2,
        )
        if len(formatted_clean) < minimum_safe_length:
            return False

    return True


def formatter_node(state: AgentState) -> dict:
    """Format the agent response as clean markdown."""
    response_text = state.get("final_response", "")
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")
    nodes = list(state.get("nodes_executed", []))
    nodes.append("formatter_node")

    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    logger.info(
        "response.boundary.formatter_input length=%d sha256_16=%s",
        len(response_text),
        _digest(response_text),
    )
    formatter_trace = {
        "input": {
            "length": len(response_text),
            "sha256_16": _digest(response_text),
        },
    }

    # Always sanitize handoff phrases
    response_text = sanitize_handoff_phrases(response_text)

    # Smart passthrough — skip LLM if already formatted or very short
    if not response_text or _already_formatted(response_text):
        logger.info(
            "response.boundary.formatter_output passthrough=true length=%d sha256_16=%s",
            len(response_text),
            _digest(response_text),
        )
        formatter_trace["output"] = {
            "passthrough": True,
            "length": len(response_text),
            "sha256_16": _digest(response_text),
        }
        update_trace(
            user_id,
            conversation_id,
            section="formatter",
            value=formatter_trace,
        )
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

        if not _is_safe_formatted_output(response_text, formatted):
            logger.warning(
                "Formatter output failed integrity validation; using original response. "
                "original_length=%d formatted_length=%d",
                len(response_text),
                len(formatted),
            )
            formatted = response_text
    except Exception:
        logger.exception("Formatter LLM call failed; using original response.")
        formatted = response_text

    logger.info(
        "response.boundary.formatter_output passthrough=false length=%d sha256_16=%s",
        len(formatted),
        _digest(formatted),
    )
    formatter_trace["output"] = {
        "passthrough": False,
        "length": len(formatted),
        "sha256_16": _digest(formatted),
    }
    update_trace(
        user_id,
        conversation_id,
        section="formatter",
        value=formatter_trace,
    )

    return {
        "final_response": formatted,
        "nodes_executed": nodes,
    }
