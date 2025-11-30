"""Lending intent definition and validation."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from src.agents.lending.config import LendingConfig

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
class LendingIntent:
    user_id: str
    conversation_id: str
    action: Optional[str] = None
    network: Optional[str] = None
    asset: Optional[str] = None
    amount: Optional[Decimal] = None
    updated_at: float = field(default_factory=lambda: time.time())

    def touch(self) -> None:
        self.updated_at = time.time()

    def is_complete(self) -> bool:
        return all(
            [
                self.action,
                self.network,
                self.asset,
                self.amount is not None,
            ]
        )

    def missing_fields(self) -> List[str]:
        fields: List[str] = []
        if not self.action:
            fields.append("action")
        if not self.network:
            fields.append("network")
        if not self.asset:
            fields.append("asset")
        if self.amount is None:
            fields.append("amount")
        return fields

    def amount_as_str(self) -> Optional[str]:
        if self.amount is None:
            return None
        return _format_decimal(self.amount)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "action": self.action,
            "network": self.network,
            "asset": self.asset,
            "amount": self.amount_as_str(),
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
            "network": self.network,
            "asset": self.asset,
            "amount": self.amount_as_str(),
        }
        if error:
            summary["error"] = error
        return summary

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LendingIntent":
        amount = _to_decimal(data.get("amount"))
        intent = cls(
            user_id=(data.get("user_id") or "").strip(),
            conversation_id=(data.get("conversation_id") or "").strip(),
            action=data.get("action"),
            network=data.get("network"),
            asset=data.get("asset"),
            amount=amount,
        )
        intent.updated_at = float(data.get("updated_at", time.time()))
        return intent
