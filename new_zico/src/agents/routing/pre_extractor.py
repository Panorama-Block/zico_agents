"""
Pre-LLM parameter extraction via compiled regex patterns.

Extracts structured fields from raw user text *before* the LLM is invoked,
reducing the number of required tool calls and saving tokens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class PreExtractedParams:
    """Fields that could be parsed from the user message."""
    amount: Optional[Decimal] = None
    from_token: Optional[str] = None
    to_token: Optional[str] = None
    from_network: Optional[str] = None
    to_network: Optional[str] = None
    action: Optional[str] = None   # supply, borrow, stake, …

    def has_any(self) -> bool:
        return any(
            v is not None
            for v in (
                self.amount, self.from_token, self.to_token,
                self.from_network, self.to_network, self.action,
            )
        )

    def to_hint(self) -> str:
        """Produce a concise system-message hint for the LLM."""
        parts: list[str] = []
        if self.action:
            parts.append(f"action={self.action}")
        if self.from_token:
            parts.append(f"from_token={self.from_token}")
        if self.to_token:
            parts.append(f"to_token={self.to_token}")
        if self.from_network:
            parts.append(f"from_network={self.from_network}")
        if self.to_network:
            parts.append(f"to_network={self.to_network}")
        if self.amount is not None:
            parts.append(f"amount={self.amount}")
        if not parts:
            return ""
        return (
            "Pre-extracted parameters from the user message: "
            + ", ".join(parts)
            + ". Validate these with the appropriate tool."
        )


# ---------------------------------------------------------------------------
# Compiled patterns (module-level for zero per-call overhead)
# ---------------------------------------------------------------------------

_SWAP_PATTERN = re.compile(
    r"(?:swap|exchange|convert|trade|troque|trocar)\s+"
    r"(?:(\d+(?:[.,]\d+)?)\s+)?"       # optional amount
    r"(\w+)\s+"                          # from_token
    r"(?:for|to|into|por|para)\s+"
    r"(\w+)"                             # to_token
    r"(?:\s+(?:on|na|no|em)\s+(\S+))?",  # optional network
    re.IGNORECASE,
)

_LENDING_PATTERN = re.compile(
    r"(supply|borrow|repay|withdraw|deposit|lend)\s+"
    r"(?:(\d+(?:[.,]\d+)?)\s+)?"
    r"(\w+)"
    r"(?:\s+(?:on|na|no|em)\s+(\S+))?",
    re.IGNORECASE,
)

_STAKING_PATTERN = re.compile(
    r"(stake|unstake)\s+"
    r"(?:(\d+(?:[.,]\d+)?)\s+)?"
    r"(\w+)?"
    r"(?:\s+(?:on|na|no|em)\s+(\S+))?",
    re.IGNORECASE,
)

# Standalone amount + token (e.g. "100 USDC", "0.5 ETH")
_AMOUNT_TOKEN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s+([A-Za-z]{2,10})\b",
)

# Network mention (e.g. "on Avalanche", "na Base")
_NETWORK_MENTION = re.compile(
    r"(?:on|na|no|em)\s+(\S+)",
    re.IGNORECASE,
)


def _safe_decimal(raw: str | None) -> Optional[Decimal]:
    if not raw:
        return None
    try:
        return Decimal(raw.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def pre_extract(text: str, intent: str) -> PreExtractedParams:
    """
    Attempt to extract structured fields from *text* given *intent*.

    Returns a ``PreExtractedParams`` (may be empty if nothing was matched).
    """
    params = PreExtractedParams()

    if intent == "swap":
        m = _SWAP_PATTERN.search(text)
        if m:
            params.amount = _safe_decimal(m.group(1))
            params.from_token = m.group(2).upper()
            params.to_token = m.group(3).upper()
            if m.group(4):
                params.from_network = m.group(4).lower()
        else:
            # Try to extract at least amount + token
            am = _AMOUNT_TOKEN.search(text)
            if am:
                params.amount = _safe_decimal(am.group(1))
                params.from_token = am.group(2).upper()
            nm = _NETWORK_MENTION.search(text)
            if nm:
                params.from_network = nm.group(1).lower()

    elif intent == "lending":
        m = _LENDING_PATTERN.search(text)
        if m:
            params.action = m.group(1).lower()
            if params.action == "deposit":
                params.action = "supply"
            params.amount = _safe_decimal(m.group(2))
            params.from_token = m.group(3).upper()
            if m.group(4):
                params.from_network = m.group(4).lower()

    elif intent == "staking":
        m = _STAKING_PATTERN.search(text)
        if m:
            params.action = m.group(1).lower()
            params.amount = _safe_decimal(m.group(2))
            if m.group(3):
                params.from_token = m.group(3).upper()

    elif intent == "dca":
        # DCA is complex; just try to extract token pair
        am = _AMOUNT_TOKEN.search(text)
        if am:
            params.amount = _safe_decimal(am.group(1))
            params.from_token = am.group(2).upper()
        # Look for "to TOKEN"
        to_m = re.search(r"(?:to|into|para)\s+([A-Za-z]{2,10})\b", text, re.IGNORECASE)
        if to_m:
            params.to_token = to_m.group(1).upper()

    return params
