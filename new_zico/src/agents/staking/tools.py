"""Staking tools that manage a conversational staking intent for Lido on Ethereum."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from src.agents.metadata import metadata
from src.agents.staking.config import StakingConfig
from src.agents.staking.intent import StakingIntent, _to_decimal
from src.agents.staking.storage import StakingStateRepository


# ---------- Helpers ----------
_STORE = StakingStateRepository.instance()
logger = logging.getLogger(__name__)


# ---------- Staking session context ----------
_CURRENT_SESSION: ContextVar[tuple[str, str]] = ContextVar(
    "_current_staking_session",
    default=("", ""),
)


def set_current_staking_session(user_id: Optional[str], conversation_id: Optional[str]) -> None:
    """Store the active staking session for tool calls executed by the agent."""

    resolved_user = (user_id or "").strip()
    resolved_conversation = (conversation_id or "").strip()
    if not resolved_user:
        raise ValueError("staking_agent requires 'user_id' to identify the staking session.")
    if not resolved_conversation:
        raise ValueError("staking_agent requires 'conversation_id' to identify the staking session.")
    _CURRENT_SESSION.set((resolved_user, resolved_conversation))


@contextmanager
def staking_session(user_id: Optional[str], conversation_id: Optional[str]):
    """Context manager that guarantees session scoping for staking tool calls."""

    set_current_staking_session(user_id, conversation_id)
    try:
        yield
    finally:
        clear_current_staking_session()


def clear_current_staking_session() -> None:
    """Reset the active staking session after the agent finishes handling a message."""

    _CURRENT_SESSION.set(("", ""))


def _resolve_session(user_id: Optional[str], conversation_id: Optional[str]) -> tuple[str, str]:
    active_user, active_conversation = _CURRENT_SESSION.get()
    resolved_user = (user_id or active_user or "").strip()
    resolved_conversation = (conversation_id or active_conversation or "").strip()
    if not resolved_user:
        raise ValueError("user_id is required for staking operations.")
    if not resolved_conversation:
        raise ValueError("conversation_id is required for staking operations.")
    return resolved_user, resolved_conversation


def _load_intent(user_id: str, conversation_id: str) -> StakingIntent:
    stored = _STORE.load_intent(user_id, conversation_id)
    if stored:
        intent = StakingIntent.from_dict(stored)
        intent.user_id = user_id
        intent.conversation_id = conversation_id
        return intent
    return StakingIntent(user_id=user_id, conversation_id=conversation_id)


# ---------- Pydantic input schema ----------
class UpdateStakingIntentInput(BaseModel):
    user_id: Optional[str] = Field(
        default=None,
        description="Stable ID for the end user / chat session. Optional if context manager is set.",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation identifier to scope staking intents within a user.",
    )
    action: Optional[str] = Field(
        default=None,
        description="The staking action: 'stake' (ETH -> stETH) or 'unstake' (stETH -> ETH)",
    )
    amount: Optional[Decimal] = Field(
        default=None,
        gt=Decimal("0"),
        description="The amount to stake or unstake",
    )

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
def _validate_action(action: Optional[str]) -> Optional[str]:
    if action is None:
        return None
    return StakingConfig.validate_action(action)


def _validate_amount(amount: Optional[Decimal], action: Optional[str]) -> Optional[Decimal]:
    if amount is None:
        return None
    if action is None:
        raise ValueError("Please specify the action (stake or unstake) before providing an amount.")

    min_amount = Decimal(StakingConfig.get_min_amount(action))
    if amount < min_amount:
        input_token = StakingConfig.get_input_token(action)
        raise ValueError(f"Minimum amount for {action} is {min_amount} {input_token}.")

    return amount


# ---------- Output helpers ----------
def _store_staking_metadata(
    intent: StakingIntent,
    ask: Optional[str],
    done: bool,
    error: Optional[str],
    choices: Optional[List[str]] = None,
) -> Dict[str, Any]:
    intent.touch()
    missing = intent.missing_fields()
    next_field = missing[0] if missing else None
    meta: Dict[str, Any] = {
        "event": "staking_intent_ready" if done else "staking_intent_pending",
        "status": "ready" if done else "collecting",
        "action": intent.action,
        "amount": intent.amount_as_str(),
        "network": intent.network,
        "protocol": intent.protocol,
        "chain_id": intent.chain_id,
        "input_token": intent.get_input_token() if intent.action else None,
        "output_token": intent.get_output_token() if intent.action else None,
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
    metadata.set_staking_agent(meta, intent.user_id, intent.conversation_id)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Staking metadata stored for user=%s conversation=%s done=%s error=%s meta=%s",
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
    intent: StakingIntent,
    ask: Optional[str],
    choices: Optional[List[str]] = None,
    done: bool = False,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    meta = _store_staking_metadata(intent, ask, done, error, choices)

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
                "amount",
                "network",
                "protocol",
                "chain_id",
                "input_token",
                "output_token",
                "user_id",
                "conversation_id",
                "history",
            )
            if meta.get(key) is not None
        }
    return payload


# ---------- Core tool ----------
@tool("update_staking_intent", args_schema=UpdateStakingIntentInput)
def update_staking_intent_tool(
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    action: Optional[str] = None,
    amount: Optional[Decimal] = None,
):
    """Update the staking intent and surface the next question or final metadata.

    Call this tool whenever the user provides new staking details. Supply only the
    fields that were mentioned in the latest message (leave the others as None)
    and keep calling it until the response event becomes 'staking_intent_ready'.

    Staking is done via Lido protocol on Ethereum Mainnet:
    - stake: Convert ETH to stETH and start earning rewards
    - unstake: Convert stETH back to ETH
    """

    resolved_user, resolved_conversation = _resolve_session(user_id, conversation_id)
    intent = _load_intent(resolved_user, resolved_conversation)
    intent.user_id = resolved_user
    intent.conversation_id = resolved_conversation

    try:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "update_staking_intent_tool input user=%s conversation=%s action=%s amount=%s",
                user_id,
                conversation_id,
                action,
                amount,
            )

        if action is not None:
            intent.action = _validate_action(action)

        if intent.action is None:
            return _response(
                intent,
                "What would you like to do? Stake ETH to earn rewards, or unstake stETH back to ETH?",
                StakingConfig.SUPPORTED_ACTIONS,
            )

        if amount is not None:
            intent.amount = _validate_amount(amount, intent.action)

        if intent.amount is None:
            input_token = intent.get_input_token()
            return _response(intent, f"How much {input_token} do you want to {intent.action}?")

    except ValueError as exc:
        message = str(exc)
        if logger.isEnabledFor(logging.INFO):
            logger.info(
                "Staking intent validation issue for user=%s conversation=%s: %s",
                intent.user_id,
                intent.conversation_id,
                message,
            )
        return _response(intent, "Please correct the input.", error=message)
    except Exception as exc:
        logger.exception(
            "Unexpected error updating staking intent for user=%s conversation=%s",
            intent.user_id,
            intent.conversation_id,
        )
        return _response(intent, "Please try again with the staking details.", error=str(exc))

    response = _response(intent, ask=None, done=True)
    return response


@tool("get_staking_info")
def get_staking_info_tool():
    """Get information about the staking service (Lido on Ethereum).

    Returns details about the supported staking protocol, network, and tokens.
    """
    return {
        "protocol": StakingConfig.PROTOCOL,
        "network": StakingConfig.NETWORK,
        "chain_id": StakingConfig.CHAIN_ID,
        "supported_actions": StakingConfig.SUPPORTED_ACTIONS,
        "tokens": {
            "stake": {
                "input": "ETH",
                "output": "stETH",
                "description": "Stake ETH to receive stETH and earn rewards",
            },
            "unstake": {
                "input": "stETH",
                "output": "ETH",
                "description": "Unstake stETH to receive ETH back",
            },
        },
        "min_amounts": {
            "stake": StakingConfig.MIN_STAKE_AMOUNT,
            "unstake": StakingConfig.MIN_UNSTAKE_AMOUNT,
        },
        "info": "Lido is a liquid staking solution for Ethereum. When you stake ETH, you receive stETH which accrues staking rewards automatically.",
    }


def get_tools():
    return [update_staking_intent_tool, get_staking_info_tool]
