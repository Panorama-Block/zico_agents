"""Lending tools that manage a conversational lending intent."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from src.agents.metadata import metadata
from src.agents.lending.config import LendingConfig
from src.agents.lending.intent import LendingIntent, _to_decimal
from src.agents.lending.storage import LendingStateRepository


# ---------- Helpers ----------
_STORE = LendingStateRepository.instance()
logger = logging.getLogger(__name__)


# ---------- Lending session context ----------
_CURRENT_SESSION: ContextVar[tuple[str, str]] = ContextVar(
    "_current_lending_session",
    default=("", ""),
)


def set_current_lending_session(user_id: Optional[str], conversation_id: Optional[str]) -> None:
    """Store the active lending session for tool calls executed by the agent."""

    resolved_user = (user_id or "").strip()
    resolved_conversation = (conversation_id or "").strip()
    if not resolved_user:
        raise ValueError("lending_agent requires 'user_id' to identify the lending session.")
    if not resolved_conversation:
        raise ValueError("lending_agent requires 'conversation_id' to identify the lending session.")
    _CURRENT_SESSION.set((resolved_user, resolved_conversation))


@contextmanager
def lending_session(user_id: Optional[str], conversation_id: Optional[str]):
    """Context manager that guarantees session scoping for lending tool calls."""

    set_current_lending_session(user_id, conversation_id)
    try:
        yield
    finally:
        clear_current_lending_session()


def clear_current_lending_session() -> None:
    """Reset the active lending session after the agent finishes handling a message."""

    _CURRENT_SESSION.set(("", ""))


def _resolve_session(user_id: Optional[str], conversation_id: Optional[str]) -> tuple[str, str]:
    active_user, active_conversation = _CURRENT_SESSION.get()
    resolved_user = (user_id or active_user or "").strip()
    resolved_conversation = (conversation_id or active_conversation or "").strip()
    if not resolved_user:
        raise ValueError("user_id is required for lending operations.")
    if not resolved_conversation:
        raise ValueError("conversation_id is required for lending operations.")
    return resolved_user, resolved_conversation


def _load_intent(user_id: str, conversation_id: str) -> LendingIntent:
    stored = _STORE.load_intent(user_id, conversation_id)
    if stored:
        intent = LendingIntent.from_dict(stored)
        intent.user_id = user_id
        intent.conversation_id = conversation_id
        return intent
    return LendingIntent(user_id=user_id, conversation_id=conversation_id)


# ---------- Pydantic input schema ----------
class UpdateLendingIntentInput(BaseModel):
    user_id: Optional[str] = Field(
        default=None,
        description="Stable ID for the end user / chat session. Optional if context manager is set.",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation identifier to scope lending intents within a user.",
    )
    action: Optional[str] = None
    network: Optional[str] = None
    asset: Optional[str] = None
    amount: Optional[Decimal] = Field(None, gt=Decimal("0"))

    @field_validator("network", mode="before")
    @classmethod
    def _norm_network(cls, value: Optional[str]) -> Optional[str]:
        return value.lower() if isinstance(value, str) else value

    @field_validator("asset", mode="before")
    @classmethod
    def _norm_asset(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if isinstance(value, str) else value
    
    @field_validator("action", mode="before")
    @classmethod
    def _norm_action(cls, value: Optional[str]) -> Optional[str]:
        return value.lower() if isinstance(value, str) else value

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
    return LendingConfig.validate_network(network)


def _validate_asset(asset: Optional[str], network: Optional[str]) -> Optional[str]:
    if asset is None:
        return None
    if network is None:
        raise ValueError("Please provide the network before choosing an asset.")
    return LendingConfig.validate_asset(asset, network)

def _validate_action(action: Optional[str]) -> Optional[str]:
    if action is None:
        return None
    return LendingConfig.validate_action(action)


# ---------- Output helpers ----------
def _store_lending_metadata(
    intent: LendingIntent,
    ask: Optional[str],
    done: bool,
    error: Optional[str],
    choices: Optional[List[str]] = None,
) -> Dict[str, Any]:
    intent.touch()
    missing = intent.missing_fields()
    next_field = missing[0] if missing else None
    meta: Dict[str, Any] = {
        "event": "lending_intent_ready" if done else "lending_intent_pending",
        "status": "ready" if done else "collecting",
        "action": intent.action,
        "network": intent.network,
        "asset": intent.asset,
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
    metadata.set_lending_agent(meta, intent.user_id, intent.conversation_id)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Lending metadata stored for user=%s conversation=%s done=%s error=%s meta=%s",
            intent.user_id,
            intent.conversation_id,
            done,
            error,
            meta,
        )
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
    intent: LendingIntent,
    ask: Optional[str],
    choices: Optional[List[str]] = None,
    done: bool = False,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    meta = _store_lending_metadata(intent, ask, done, error, choices)

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
                "action",
                "network",
                "asset",
                "amount",
                "user_id",
                "conversation_id",
                "history",
            )
            if meta.get(key) is not None
        }
    return payload


# ---------- Core tool ----------
@tool("update_lending_intent", args_schema=UpdateLendingIntentInput)
def update_lending_intent_tool(
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    action: Optional[str] = None,
    network: Optional[str] = None,
    asset: Optional[str] = None,
    amount: Optional[Decimal] = None,
):
    """Update the lending intent and surface the next question or final metadata.

    Call this tool whenever the user provides new lending details. Supply only the
    fields that were mentioned in the latest message (leave the others as None)
    and keep calling it until the response event becomes 'lending_intent_ready'.
    """

    resolved_user, resolved_conversation = _resolve_session(user_id, conversation_id)
    intent = _load_intent(resolved_user, resolved_conversation)
    intent.user_id = resolved_user
    intent.conversation_id = resolved_conversation

    try:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "update_lending_intent_tool input user=%s conversation=%s action=%s network=%s "
                "asset=%s amount=%s",
                user_id,
                conversation_id,
                action,
                network,
                asset,
                amount,
            )

        if action is not None:
            intent.action = _validate_action(action)

        if network is not None:
            canonical_net = _validate_network(network)
            if canonical_net != intent.network:
                intent.network = canonical_net
                # Re-validate asset if network changed
                if intent.asset:
                    try:
                        LendingConfig.validate_asset(intent.asset, canonical_net)
                    except ValueError:
                        intent.asset = None
        
        if intent.action is None:
             return _response(
                intent,
                "What would you like to do? (supply, borrow, repay, withdraw)",
                LendingConfig.SUPPORTED_ACTIONS,
            )

        if intent.network is None and network is not None:
             # User tried to set network but maybe it was invalid or just checking
             pass

        if intent.network is None:
             return _response(
                intent,
                "On which network?",
                LendingConfig.list_networks(),
            )

        if asset is not None:
            intent.asset = _validate_asset(asset, intent.network)

        if intent.asset is None:
            return _response(
                intent,
                f"Which asset on {intent.network}?",
                LendingConfig.list_assets(intent.network),
            )

        if amount is not None:
            intent.amount = amount # Basic validation done in pydantic

        if intent.amount is None:
            return _response(intent, f"How much {intent.asset}?")

    except ValueError as exc:
        message = str(exc)
        if logger.isEnabledFor(logging.INFO):
            logger.info(
                "Lending intent validation issue for user=%s conversation=%s: %s",
                intent.user_id,
                intent.conversation_id,
                message,
            )
        return _response(intent, "Please correct the input.", error=message)
    except Exception as exc:
        logger.exception(
            "Unexpected error updating lending intent for user=%s conversation=%s",
            intent.user_id,
            intent.conversation_id,
        )
        return _response(intent, "Please try again with the lending details.", error=str(exc))

    response = _response(intent, ask=None, done=True)
    return response


class ListLendingAssetsInput(BaseModel):
    network: str

    @field_validator("network", mode="before")
    @classmethod
    def _norm_network(cls, value: str) -> str:
        return value.lower() if isinstance(value, str) else value


@tool("list_lending_assets", args_schema=ListLendingAssetsInput)
def list_lending_assets_tool(network: str):
    """List the supported lending assets for a given network."""

    try:
        canonical = _validate_network(network)
        assets = LendingConfig.list_assets(canonical)
        return {
            "network": canonical,
            "assets": assets,
        }
    except ValueError as exc:
        return {
            "error": str(exc),
            "choices": LendingConfig.list_networks(),
        }


@tool("list_lending_networks")
def list_lending_networks_tool():
    """List supported lending networks."""

    return {"networks": LendingConfig.list_networks()}


def get_tools():
    return [update_lending_intent_tool, list_lending_assets_tool, list_lending_networks_tool]
