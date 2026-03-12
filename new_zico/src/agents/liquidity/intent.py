"""Liquidity intent definition and validation."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from src.agents.liquidity.config import LiquidityConfig


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
class LiquidityIntent:
    user_id: str
    conversation_id: str
    action: Optional[str] = None  # enter, exit, claim (canonical)
    pool_id: Optional[str] = None  # canonical pool id (e.g. "weth-usdc-volatile")
    amount: Optional[Decimal] = None  # primary amount (token_a for enter, LP tokens for exit)
    use_max: bool = False
    updated_at: float = field(default_factory=lambda: time.time())

    # Fixed values
    network: str = field(default_factory=lambda: LiquidityConfig.NETWORK)
    protocol: str = field(default_factory=lambda: LiquidityConfig.PROTOCOL)
    chain_id: int = field(default_factory=lambda: LiquidityConfig.CHAIN_ID)

    def touch(self) -> None:
        self.updated_at = time.time()

    def is_complete(self) -> bool:
        if self.action == "claim":
            return self.action is not None and self.pool_id is not None
        return all([
            self.action,
            self.pool_id,
            self.amount is not None,
        ])

    def missing_fields(self) -> List[str]:
        fields: List[str] = []
        if not self.action:
            fields.append("action")
        if not self.pool_id:
            fields.append("pool_id")
        if self.action != "claim" and self.amount is None and not self.use_max:
            fields.append("amount")
        return fields

    def amount_as_str(self) -> Optional[str]:
        if self.amount is None:
            return None
        return _format_decimal(self.amount)

    def get_pool_tokens(self) -> tuple[Optional[str], Optional[str]]:
        if not self.pool_id:
            return None, None
        pool = LiquidityConfig.get_pool(self.pool_id)
        if not pool:
            return None, None
        return pool["token_a"], pool["token_b"]

    def is_stable(self) -> Optional[bool]:
        if not self.pool_id:
            return None
        pool = LiquidityConfig.get_pool(self.pool_id)
        return pool["stable"] if pool else None

    def to_dict(self) -> Dict[str, Any]:
        token_a, token_b = self.get_pool_tokens()
        return {
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "action": self.action,
            "pool_id": self.pool_id,
            "amount": self.amount_as_str(),
            "use_max": self.use_max,
            "network": self.network,
            "protocol": self.protocol,
            "chain_id": self.chain_id,
            "token_a": token_a,
            "token_b": token_b,
            "stable": self.is_stable(),
            "updated_at": self.updated_at,
        }

    def to_public(self) -> Dict[str, Optional[str]]:
        public = self.to_dict()
        public["amount"] = self.amount_as_str()
        return public

    def to_summary(self, status: str, error: Optional[str] = None) -> Dict[str, Any]:
        token_a, token_b = self.get_pool_tokens()
        summary: Dict[str, Any] = {
            "status": status,
            "action": self.action,
            "pool_id": self.pool_id,
            "amount": self.amount_as_str(),
            "use_max": self.use_max,
            "network": self.network,
            "protocol": self.protocol,
            "token_a": token_a,
            "token_b": token_b,
        }
        if error:
            summary["error"] = error
        return summary

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LiquidityIntent":
        amount = _to_decimal(data.get("amount"))
        intent = cls(
            user_id=(data.get("user_id") or "").strip(),
            conversation_id=(data.get("conversation_id") or "").strip(),
            action=data.get("action"),
            pool_id=data.get("pool_id"),
            amount=amount,
            use_max=bool(data.get("use_max") or False),
        )
        intent.updated_at = float(data.get("updated_at", time.time()))
        return intent
