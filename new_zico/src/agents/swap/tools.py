"""Swap tools that manage a conversational swap intent."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from src.agents.metadata import metadata
from src.agents.swap.config import SwapConfig

# ---------- In-memory intent store (swap session) ----------
# Replace with persistent storage if the agent runs in multiple instances.
_INTENTS: Dict[str, "SwapIntent"] = {}
_DEFAULT_USER_ID = "__default_swap_user__"


@dataclass
class SwapIntent:
    user_id: str = _DEFAULT_USER_ID
    from_network: Optional[str] = None
    from_token: Optional[str] = None
    to_network: Optional[str] = None
    to_token: Optional[str] = None
    amount: Optional[float] = None

    def is_complete(self) -> bool:
        return all(
            [
                self.from_network,
                self.from_token,
                self.to_network,
                self.to_token,
                self.amount,
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


# ---------- Pydantic input schema ----------
class UpdateSwapIntentInput(BaseModel):
    user_id: Optional[str] = Field(
        default=None,
        description="Stable ID for the end user / chat session. Optional, but required for multi-user disambiguation.",
    )
    from_network: Optional[str] = None
    from_token: Optional[str] = None
    to_network: Optional[str] = None
    to_token: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)

    @field_validator("from_network", "to_network", mode="before")
    @classmethod
    def _norm_network(cls, value: Optional[str]) -> Optional[str]:
        return value.lower() if isinstance(value, str) else value

    @field_validator("from_token", "to_token", mode="before")
    @classmethod
    def _norm_token(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if isinstance(value, str) else value


# ---------- Output helpers ----------
def _response(
    intent: SwapIntent,
    ask: Optional[str],
    choices: Optional[List[str]] = None,
    done: bool = False,
    error: Optional[str] = None,
) -> Dict[str, object]:
    """Consistent payload for the UI layer."""

    payload: Dict[str, object] = {
        "event": "swap_intent_ready" if done else "ask_user",
        "intent": asdict(intent),
        "ask": ask,
        "choices": choices or [],
        "error": error,
    }
    if done:
        payload["metadata"] = {
            "event": "swap_intent_ready",
            "from_network": intent.from_network,
            "from_token": intent.from_token,
            "to_network": intent.to_network,
            "to_token": intent.to_token,
            "amount": intent.amount,
        }
    return payload


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


# ---------- Core tool ----------
@tool("update_swap_intent", args_schema=UpdateSwapIntentInput)
def update_swap_intent_tool(
    user_id: Optional[str] = None,
    from_network: Optional[str] = None,
    from_token: Optional[str] = None,
    to_network: Optional[str] = None,
    to_token: Optional[str] = None,
    amount: Optional[float] = None,
):
    """Update the swap intent and surface the next question or final metadata.

    Call this tool whenever the user provides new swap details. Supply only the
    fields that were mentioned in the latest message (leave the others as None)
    and keep calling it until the response event becomes 'swap_intent_ready'.
    """

    intent_key = user_id or _DEFAULT_USER_ID
    intent = _INTENTS.get(intent_key) or SwapIntent(user_id=intent_key)
    if user_id:
        intent.user_id = user_id
    _INTENTS[intent_key] = intent

    try:
        if from_network is not None:
            intent.from_network = _validate_network(from_network)

        if intent.from_network is None and from_token is not None:
            return _response(
                intent,
                "From which network?",
                list(SwapConfig.list_networks()),
            )

        if from_token is not None:
            intent.from_token = _validate_token(from_token, intent.from_network)

        if to_network is not None:
            intent.to_network = _validate_network(to_network)

        if intent.to_network is None and to_token is not None:
            return _response(
                intent,
                "To which network?",
                list(SwapConfig.list_networks()),
            )

        if to_token is not None:
            intent.to_token = _validate_token(to_token, intent.to_network)

        if amount is not None:
            intent.amount = amount

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

    meta = {
        "event": "swap_intent_ready",
        "from_network": intent.from_network,
        "from_token": intent.from_token,
        "to_network": intent.to_network,
        "to_token": intent.to_token,
        "amount": intent.amount,
    }
    metadata.set_swap_agent(meta)
    return _response(intent, ask=None, done=True)


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
        return {
            "network": canonical,
            "tokens": list(SwapConfig.list_tokens(canonical)),
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
