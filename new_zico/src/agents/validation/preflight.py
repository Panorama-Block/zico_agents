"""
Pre-flight Pydantic validators for DeFi operations.

These run *before* the LLM is invoked and catch obviously invalid inputs
early, saving tokens and latency.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ValidationError, field_validator, model_validator


# ---------------------------------------------------------------------------
# Swap
# ---------------------------------------------------------------------------

class SwapPreflightCheck(BaseModel):
    from_network: Optional[str] = None
    from_token: Optional[str] = None
    to_network: Optional[str] = None
    to_token: Optional[str] = None
    amount: Optional[Decimal] = None

    @field_validator("amount", mode="before")
    @classmethod
    def _validate_amount(cls, v):
        if v is None:
            return v
        d = Decimal(str(v))
        if d <= 0:
            raise ValueError("Amount must be positive")
        if d > Decimal("10000000"):
            raise ValueError("Amount exceeds safety maximum (10 000 000)")
        return d

    @model_validator(mode="after")
    def _validate_not_self_swap(self):
        if (
            self.from_token
            and self.to_token
            and self.from_token.upper() == self.to_token.upper()
            and self.from_network
            and self.to_network
            and self.from_network.lower() == self.to_network.lower()
        ):
            raise ValueError("Cannot swap a token for itself on the same network")
        return self


# ---------------------------------------------------------------------------
# Lending
# ---------------------------------------------------------------------------

_VALID_LENDING_ACTIONS = {"supply", "borrow", "repay", "withdraw", "deposit"}


class LendingPreflightCheck(BaseModel):
    action: Optional[str] = None
    network: Optional[str] = None
    asset: Optional[str] = None
    amount: Optional[Decimal] = None

    @field_validator("action", mode="before")
    @classmethod
    def _normalize_action(cls, v):
        if v is None:
            return v
        v = str(v).lower().strip()
        if v == "deposit":
            v = "supply"
        if v not in _VALID_LENDING_ACTIONS:
            raise ValueError(f"Invalid lending action: {v}")
        return v

    @field_validator("amount", mode="before")
    @classmethod
    def _validate_amount(cls, v):
        if v is None:
            return v
        d = Decimal(str(v))
        if d <= 0:
            raise ValueError("Amount must be positive")
        if d > Decimal("100000000"):
            raise ValueError("Amount exceeds safety maximum (100 000 000)")
        return d


# ---------------------------------------------------------------------------
# Staking
# ---------------------------------------------------------------------------

class StakingPreflightCheck(BaseModel):
    action: Optional[str] = None
    amount: Optional[Decimal] = None

    @field_validator("action", mode="before")
    @classmethod
    def _normalize_action(cls, v):
        if v is None:
            return v
        v = str(v).lower().strip()
        if v not in ("stake", "unstake"):
            raise ValueError(f"Invalid staking action: {v}")
        return v

    @field_validator("amount", mode="before")
    @classmethod
    def _validate_amount(cls, v):
        if v is None:
            return v
        d = Decimal(str(v))
        if d <= 0:
            raise ValueError("Amount must be positive")
        if d > Decimal("1000000"):
            raise ValueError("Amount exceeds safety maximum (1 000 000)")
        return d


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def run_preflight(intent: str, params: dict) -> List[str]:
    """
    Run preflight validation for *intent* and return a list of error
    messages (empty if everything is valid).
    """
    errors: List[str] = []
    try:
        if intent == "swap":
            SwapPreflightCheck(**params)
        elif intent == "lending":
            LendingPreflightCheck(**params)
        elif intent == "staking":
            StakingPreflightCheck(**params)
    except ValidationError as exc:
        # Extract only the human-readable messages from Pydantic errors
        for err in exc.errors():
            msg = err.get("msg", "")
            # Strip Pydantic's "Value error, " prefix if present
            if msg.lower().startswith("value error, "):
                msg = msg[len("Value error, "):]
            if msg:
                errors.append(msg)
    except Exception as exc:
        errors.append(str(exc))
    return errors
