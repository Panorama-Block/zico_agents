"""
Conversation windowing — keeps context size bounded.

Strategy:
1. Always preserve the last *max_recent* messages in full.
2. Older messages are summarised into a single system block using a
   lightweight (FAST tier) LLM call.
3. If no summariser is provided, older messages are simply dropped.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

DEFAULT_MAX_RECENT = 8


def prepare_context(
    messages: List[Dict[str, Any]],
    *,
    max_recent: int = DEFAULT_MAX_RECENT,
    summarizer_llm: Optional[BaseChatModel] = None,
) -> List[Dict[str, Any]]:
    """
    Prepare a bounded context window from *messages*.

    Returns a list of message dicts ready for conversion to LangChain objects.
    """
    if len(messages) <= max_recent:
        return messages

    recent = messages[-max_recent:]
    older = messages[:-max_recent]

    if summarizer_llm and older:
        summary = _summarize(older, summarizer_llm)
        if summary:
            summary_msg: Dict[str, Any] = {
                "role": "system",
                "content": f"[Conversation summary so far]\n{summary}",
            }
            return [summary_msg] + recent

    # No summariser → just keep the recent window
    return recent


def _summarize(
    messages: List[Dict[str, Any]],
    llm: BaseChatModel,
) -> Optional[str]:
    """Summarise *messages* into a compact paragraph."""
    try:
        transcript_lines: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = (msg.get("content") or "")[:500]  # cap per message
            transcript_lines.append(f"{role}: {content}")

        transcript = "\n".join(transcript_lines[-30:])  # last 30 msgs max

        prompt = (
            "Summarise the following conversation excerpt in 2-4 concise "
            "sentences.  Preserve any DeFi operation context (tokens, "
            "networks, amounts, actions) if present.  Reply in English.\n\n"
            f"{transcript}"
        )

        response = llm.invoke([
            SystemMessage(content="You are a concise conversation summariser."),
            HumanMessage(content=prompt),
        ])
        text = getattr(response, "content", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    except Exception:
        logger.exception("Conversation summarisation failed; skipping.")

    return None
