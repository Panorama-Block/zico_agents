"""Swap tools that manage a conversational swap intent."""

from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from src.agents.metadata import metadata
from src.agents.swap.config import SwapConfig
from src.agents.swap.storage import SwapStateRepository


# ---------- Helpers ----------
_STORE = SwapStateRepository.instance()


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
class SwapIntent:
    user_id: str
    conversation_id: str
    from_network: Optional[str] = None
    from_token: Optional[str] = None
    to_network: Optional[str] = None
    to_token: Optional[str] = None
    amount: Optional[Decimal] = None
    updated_at: float = field(default_factory=lambda: time.time())

    def touch(self) -> None:
        self.updated_at = time.time()

    def is_complete(self) -> bool:
        return all(
            [
                self.from_network,
                self.from_token,
                self.to_network,
                self.to_token,
                self.amount is not None,
            ]
        )

    def missing_fields(self) -> List[str]:
        fields: List[str] = []
        if not self.from_network:
            fields.append("from_network")
        if not self.from_token:
            fields.append("from_token")
        if not self.to_network:
            fields.append("to_network")
        if not self.to_token:
            fields.append("to_token")
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
            "from_network": self.from_network,
            "from_token": self.from_token,
            "to_network": self.to_network,
            "to_token": self.to_token,
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
            "from_network": self.from_network,
            "from_token": self.from_token,
            "to_network": self.to_network,
            "to_token": self.to_token,
            "amount": self.amount_as_str(),
        }
        if error:
            summary["error"] = error
        return summary

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SwapIntent":
        amount = _to_decimal(data.get("amount"))
        intent = cls(
            user_id=(data.get("user_id") or "").strip(),
            conversation_id=(data.get("conversation_id") or "").strip(),
            from_network=data.get("from_network"),
            from_token=data.get("from_token"),
            to_network=data.get("to_network"),
            to_token=data.get("to_token"),
            amount=amount,
        )
        intent.updated_at = float(data.get("updated_at", time.time()))
        return intent


# ---------- Swap session context ----------
_CURRENT_SESSION: ContextVar[tuple[str, str]] = ContextVar(
    "_current_swap_session",
    default=("", ""),
)


def set_current_swap_session(user_id: Optional[str], conversation_id: Optional[str]) -> None:
    """Store the active swap session for tool calls executed by the agent."""

    resolved_user = (user_id or "").strip()
    resolved_conversation = (conversation_id or "").strip()
    if not resolved_user:
        raise ValueError("swap_agent requires 'user_id' to identify the swap session.")
    if not resolved_conversation:
        raise ValueError("swap_agent requires 'conversation_id' to identify the swap session.")
    _CURRENT_SESSION.set((resolved_user, resolved_conversation))


@contextmanager
def swap_session(user_id: Optional[str], conversation_id: Optional[str]):
    """Context manager that guarantees session scoping for swap tool calls."""

    set_current_swap_session(user_id, conversation_id)
    try:
        yield
    finally:
        clear_current_swap_session()


def clear_current_swap_session() -> None:
    """Reset the active swap session after the agent finishes handling a message."""

    _CURRENT_SESSION.set(("", ""))


def _resolve_session(user_id: Optional[str], conversation_id: Optional[str]) -> tuple[str, str]:
    active_user, active_conversation = _CURRENT_SESSION.get()
    resolved_user = (user_id or active_user or "").strip()
    resolved_conversation = (conversation_id or active_conversation or "").strip()
    if not resolved_user:
        raise ValueError("user_id is required for swap operations.")
    if not resolved_conversation:
        raise ValueError("conversation_id is required for swap operations.")
    return resolved_user, resolved_conversation


def _load_intent(user_id: str, conversation_id: str) -> SwapIntent:
    stored = _STORE.load_intent(user_id, conversation_id)
    if stored:
        intent = SwapIntent.from_dict(stored)
        intent.user_id = user_id
        intent.conversation_id = conversation_id
        return intent
    return SwapIntent(user_id=user_id, conversation_id=conversation_id)


# ---------- Pydantic input schema ----------
class UpdateSwapIntentInput(BaseModel):
    user_id: Optional[str] = Field(
        default=None,
        description="Stable ID for the end user / chat session. Optional if context manager is set.",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation identifier to scope swap intents within a user.",
    )
    from_network: Optional[str] = None
    from_token: Optional[str] = None
    to_network: Optional[str] = None
    to_token: Optional[str] = None
    amount: Optional[Decimal] = Field(None, gt=Decimal("0"))

    @field_validator("from_network", "to_network", mode="before")
    @classmethod
    def _norm_network(cls, value: Optional[str]) -> Optional[str]:
        return value.lower() if isinstance(value, str) else value

    @field_validator("from_token", "to_token", mode="before")
    @classmethod
    def _norm_token(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if isinstance(value, str) else value

    @field_validator("amount", mode="before")
    @classmethod
    def _norm_amount(cls, value):
        if value is None or isinstance(value, Decimal):
            return value
        decimal_value = _to_decimal(value)
        if decimal_value is None:
            raise ValueError("Amount must be a number.")
        return decimal_value


# ---------- Validation utilities ----------
def _validate_network(network: Optional[str]) -> Optional[str]:
    if network is None:
        return None
    return SwapConfig.validate_network(network)


def _validate_token(token: Optional[str], network: Optional[str]) -> Optional[str]:
    if token is None:
        return None
    if network is None:
        raise ValueError("Please provide the network before choosing a token.")
    supported = list(SwapConfig.list_tokens(network))
    if token not in supported:
        raise ValueError(
            f"Unsupported token '{token}' on {network}. Available: {supported}"
        )
    return SwapConfig.validate_or_raise(token, network)


def _validate_route(from_network: str, to_network: str) -> None:
    if hasattr(SwapConfig, "routes_supported"):
        if not SwapConfig.routes_supported(from_network, to_network):
            raise ValueError(
                f"Route {from_network} -> {to_network} is not supported."
            )


def _validate_amount(amount: Optional[Decimal], intent: SwapIntent) -> Optional[Decimal]:
    if amount is None:
        return None
    if not intent.from_network or not intent.from_token:
        raise ValueError("Provide the source network and token before specifying an amount.")

    policy = SwapConfig.get_token_policy(intent.from_network, intent.from_token)
    decimals_value = policy.get("decimals", 18)
    try:
        decimals = int(decimals_value)
    except (TypeError, ValueError):
        decimals = 18

    if decimals >= 0 and amount.as_tuple().exponent < -decimals:
        raise ValueError(
            f"Amount precision exceeds {decimals} decimal places allowed for {intent.from_token}."
        )

    minimum = _to_decimal(policy.get("min_amount"))
    maximum = _to_decimal(policy.get("max_amount"))

    if minimum is not None and amount < minimum:
        raise ValueError(
            f"The minimum amount for {intent.from_token} on {intent.from_network} is {minimum}."
        )
    if maximum is not None and amount > maximum:
        raise ValueError(
            f"The maximum amount for {intent.from_token} on {intent.from_network} is {maximum}."
        )

    return amount


# ---------- Output helpers ----------
def _store_swap_metadata(
    intent: SwapIntent,
    ask: Optional[str],
    done: bool,
    error: Optional[str],
    choices: Optional[List[str]] = None,
) -> Dict[str, Any]:
    intent.touch()
    missing = intent.missing_fields()
    next_field = missing[0] if missing else None
    meta: Dict[str, Any] = {
        "event": "swap_intent_ready" if done else "swap_intent_pending",
        "status": "ready" if done else "collecting",
        "from_network": intent.from_network,
        "from_token": intent.from_token,
        "to_network": intent.to_network,
        "to_token": intent.to_token,
        "amount": intent.amount_as_str(),
        "user_id": intent.user_id,
        "conversation_id": intent.conversation_id,
        "missing_fields": missing,
        "next_field": next_field,
        "pending_question": ask,
        "choices": list(choices or []),
        "error": error,
    }
    summary = intent.to_summary("ready" if done else "collecting", error=error) if done else None
    history = _STORE.persist_intent(
        intent.user_id,
        intent.conversation_id,
        intent.to_dict(),
        meta,
        done=done,
        summary=summary,
    )
    if history:
        meta["history"] = history
    metadata.set_swap_agent(meta, intent.user_id, intent.conversation_id)
    return meta


def _build_next_action(meta: Dict[str, Any]) -> Dict[str, Any]:
    if meta.get("status") == "ready":
        return {
            "type": "complete",
            "prompt": None,
            "field": None,
            "choices": [],
        }
    return {
        "type": "collect_field",
        "prompt": meta.get("pending_question"),
        "field": meta.get("next_field"),
        "choices": meta.get("choices", []),
    }


def _response(
    intent: SwapIntent,
    ask: Optional[str],
    choices: Optional[List[str]] = None,
    done: bool = False,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    meta = _store_swap_metadata(intent, ask, done, error, choices)

    payload: Dict[str, Any] = {
        "event": meta.get("event"),
        "intent": intent.to_public(),
        "ask": ask,
        "choices": choices or [],
        "error": error,
        "next_action": _build_next_action(meta),
        "history": meta.get("history", []),
    }

    if done:
        payload["metadata"] = {
            key: meta.get(key)
            for key in (
                "event",
                "status",
                "from_network",
                "from_token",
                "to_network",
                "to_token",
                "amount",
                "user_id",
                "conversation_id",
                "history",
            )
            if meta.get(key) is not None
        }
    return payload


# ---------- Core tool ----------
@tool("update_swap_intent", args_schema=UpdateSwapIntentInput)
def update_swap_intent_tool(
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    from_network: Optional[str] = None,
    from_token: Optional[str] = None,
    to_network: Optional[str] = None,
    to_token: Optional[str] = None,
    amount: Optional[Decimal] = None,
):
    """Update the swap intent and surface the next question or final metadata.

    Call this tool whenever the user provides new swap details. Supply only the
    fields that were mentioned in the latest message (leave the others as None)
    and keep calling it until the response event becomes 'swap_intent_ready'.
    """

    resolved_user, resolved_conversation = _resolve_session(user_id, conversation_id)
    intent = _load_intent(resolved_user, resolved_conversation)
    intent.user_id = resolved_user
    intent.conversation_id = resolved_conversation

    try:
        if from_network is not None:
            canonical_from = _validate_network(from_network)
            if canonical_from != intent.from_network:
                intent.from_network = canonical_from
                if intent.from_token:
                    try:
                        SwapConfig.validate_or_raise(intent.from_token, canonical_from)
                    except ValueError:
                        intent.from_token = None

        if intent.from_network is None and from_token is not None:
            return _response(
                intent,
                "From which network?",
                list(SwapConfig.list_networks()),
            )

        if from_token is not None:
            intent.from_token = _validate_token(from_token, intent.from_network)

        if to_network is not None:
            canonical_to = _validate_network(to_network)
            if canonical_to != intent.to_network:
                intent.to_network = canonical_to
                if intent.to_token:
                    try:
                        SwapConfig.validate_or_raise(intent.to_token, canonical_to)
                    except ValueError:
                        intent.to_token = None

        if intent.to_network is None and to_token is not None:
            return _response(
                intent,
                "To which network?",
                list(SwapConfig.list_networks()),
            )

        if to_token is not None:
            intent.to_token = _validate_token(to_token, intent.to_network)

        if amount is not None:
            intent.amount = _validate_amount(amount, intent)

        if intent.from_network and intent.to_network:
            _validate_route(intent.from_network, intent.to_network)

    except ValueError as exc:
        message = str(exc)
        lowered = message.lower()
        if "network" in lowered:
            return _response(
                intent,
                "Choose a network.",
                list(SwapConfig.list_networks()),
                error=message,
            )
        if "token" in lowered and intent.from_network:
            return _response(
                intent,
                f"Choose a token on {intent.from_network}.",
                list(SwapConfig.list_tokens(intent.from_network)),
                error=message,
            )
        if "amount" in lowered and intent.from_token:
            return _response(
                intent,
                f"Provide a valid amount in {intent.from_token}.",
                error=message,
            )
        return _response(intent, "Please correct the input.", error=message)

    if intent.from_network is None:
        return _response(
            intent,
            "From which network?",
            list(SwapConfig.list_networks()),
        )
    if intent.from_token is None:
        return _response(
            intent,
            f"Which token on {intent.from_network}?",
            list(SwapConfig.list_tokens(intent.from_network)),
        )
    if intent.to_network is None:
        return _response(
            intent,
            "To which network?",
            list(SwapConfig.list_networks()),
        )
    if intent.to_token is None:
        return _response(
            intent,
            f"Which token on {intent.to_network}?",
            list(SwapConfig.list_tokens(intent.to_network)),
        )
    if intent.amount is None:
        denom = intent.from_token
        return _response(intent, f"What is the amount in {denom}?")

    response = _response(intent, ask=None, done=True)
    return response


class ListTokensInput(BaseModel):
    network: str

    @field_validator("network", mode="before")
    @classmethod
    def _norm_network(cls, value: str) -> str:
        return value.lower() if isinstance(value, str) else value


@tool("list_tokens", args_schema=ListTokensInput)
def list_tokens_tool(network: str):
    """List the supported tokens for a given network."""

    try:
        canonical = _validate_network(network)
        tokens = list(SwapConfig.list_tokens(canonical))
        policies = {
            token: SwapConfig.get_token_policy(canonical, token)
            for token in tokens
        }
        return {
            "network": canonical,
            "tokens": tokens,
            "policies": policies,
        }
    except ValueError as exc:
        return {
            "error": str(exc),
            "choices": list(SwapConfig.list_networks()),
        }


@tool("list_networks")
def list_networks_tool():
    """List supported networks."""

    return {"networks": list(SwapConfig.list_networks())}


def get_tools():
    return [update_swap_intent_tool, list_tokens_tool, list_networks_tool]
