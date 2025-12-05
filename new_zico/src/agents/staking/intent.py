"""Staking intent definition and validation."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from src.agents.staking.config import StakingConfig


def _format_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    exponent = normalized.as_tuple().exponent
    if exponent > 0:
        normalized = normalized.quantize(Decimal(1))
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


@dataclass
class StakingIntent:
    user_id: str
    conversation_id: str
    action: Optional[str] = None  # stake or unstake
    amount: Optional[Decimal] = None
    updated_at: float = field(default_factory=lambda: time.time())

    # Fixed values for Lido on Ethereum
    network: str = field(default_factory=lambda: StakingConfig.NETWORK)
    protocol: str = field(default_factory=lambda: StakingConfig.PROTOCOL)
    chain_id: int = field(default_factory=lambda: StakingConfig.CHAIN_ID)

    def touch(self) -> None:
        self.updated_at = time.time()

    def is_complete(self) -> bool:
        return all([
            self.action,
            self.amount is not None,
        ])

    def missing_fields(self) -> List[str]:
        fields: List[str] = []
        if not self.action:
            fields.append("action")
        if self.amount is None:
            fields.append("amount")
        return fields

    def amount_as_str(self) -> Optional[str]:
        if self.amount is None:
            return None
        return _format_decimal(self.amount)

    def get_input_token(self) -> str:
        """Get the token being sent based on action."""
        if self.action == "stake":
            return "ETH"
        return "stETH"

    def get_output_token(self) -> str:
        """Get the token being received based on action."""
        if self.action == "stake":
            return "stETH"
        return "ETH"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "action": self.action,
            "amount": self.amount_as_str(),
            "network": self.network,
            "protocol": self.protocol,
            "chain_id": self.chain_id,
            "input_token": self.get_input_token() if self.action else None,
            "output_token": self.get_output_token() if self.action else None,
            "updated_at": self.updated_at,
        }

    def to_public(self) -> Dict[str, Optional[str]]:
        public = self.to_dict()
        public["amount"] = self.amount_as_str()
        return public

    def to_summary(self, status: str, error: Optional[str] = None) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "status": status,
            "action": self.action,
            "amount": self.amount_as_str(),
            "network": self.network,
            "protocol": self.protocol,
            "input_token": self.get_input_token() if self.action else None,
            "output_token": self.get_output_token() if self.action else None,
        }
        if error:
            summary["error"] = error
        return summary

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StakingIntent":
        amount = _to_decimal(data.get("amount"))
        intent = cls(
            user_id=(data.get("user_id") or "").strip(),
            conversation_id=(data.get("conversation_id") or "").strip(),
            action=data.get("action"),
            amount=amount,
        )
        intent.updated_at = float(data.get("updated_at", time.time()))
        return intent
