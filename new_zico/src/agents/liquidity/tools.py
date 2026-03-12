"""Liquidity tools that manage a conversational liquidity intent for Aerodrome on Base."""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from src.agents.metadata import metadata
from src.agents.liquidity.config import LiquidityConfig
from src.agents.liquidity.intent import LiquidityIntent, _to_decimal
from src.agents.liquidity.storage import LiquidityStateRepository
from src.agents.portfolio.tools import get_user_portfolio_tool


# ---------- Helpers ----------
_STORE = LiquidityStateRepository.instance()
logger = logging.getLogger(__name__)
_EXECUTION_BALANCE_TTL_SECONDS = 20
_LAST_VALID_BALANCE_TTL_SECONDS = 120
_REQUEST_TIMEOUT_SECONDS = 2.5
_EXECUTION_BALANCE_CACHE: Dict[str, tuple[Dict[str, Decimal], float]] = {}
_EXECUTION_POSITION_CACHE: Dict[str, tuple[Dict[str, Decimal], float]] = {}
_LAST_VALID_BALANCES: Dict[str, tuple[Dict[str, Decimal], float]] = {}


# ---------- Liquidity session context ----------
_CURRENT_SESSION: ContextVar[tuple[str, str]] = ContextVar(
    "_current_liquidity_session",
    default=("", ""),
)


def set_current_liquidity_session(user_id: Optional[str], conversation_id: Optional[str]) -> None:
    resolved_user = (user_id or "").strip()
    resolved_conversation = (conversation_id or "").strip()
    if not resolved_user:
        raise ValueError("liquidity_agent requires 'user_id' to identify the session.")
    if not resolved_conversation:
        raise ValueError("liquidity_agent requires 'conversation_id' to identify the session.")
    _CURRENT_SESSION.set((resolved_user, resolved_conversation))


@contextmanager
def liquidity_session(user_id: Optional[str], conversation_id: Optional[str]):
    set_current_liquidity_session(user_id, conversation_id)
    try:
        yield
    finally:
        clear_current_liquidity_session()


def clear_current_liquidity_session() -> None:
    _CURRENT_SESSION.set(("", ""))


def _resolve_session(user_id: Optional[str], conversation_id: Optional[str]) -> tuple[str, str]:
    active_user, active_conversation = _CURRENT_SESSION.get()
    resolved_user = (user_id or active_user or "").strip()
    resolved_conversation = (conversation_id or active_conversation or "").strip()
    if not resolved_user:
        raise ValueError("user_id is required for liquidity operations.")
    if not resolved_conversation:
        raise ValueError("conversation_id is required for liquidity operations.")
    return resolved_user, resolved_conversation


def _load_intent(user_id: str, conversation_id: str) -> LiquidityIntent:
    stored = _STORE.load_intent(user_id, conversation_id)
    if stored:
        intent = LiquidityIntent.from_dict(stored)
        intent.user_id = user_id
        intent.conversation_id = conversation_id
        return intent
    return LiquidityIntent(user_id=user_id, conversation_id=conversation_id)


# ---------- Pydantic input schema ----------
class UpdateLiquidityIntentInput(BaseModel):
    user_id: Optional[str] = Field(
        default=None,
        description="Stable ID for the end user / chat session. Optional if context manager is set.",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation identifier to scope liquidity intents within a user.",
    )
    action: Optional[str] = Field(
        default=None,
        description="Liquidity action (canonical preferred): 'enter', 'exit', 'claim'. Legacy aliases are accepted.",
    )
    pool_id: Optional[str] = Field(
        default=None,
        description="The pool identifier, e.g. 'WETH-USDC', 'WETH-AERO', 'USDC-USDbC'",
    )
    amount: Optional[Decimal] = Field(
        default=None,
        gt=Decimal("0"),
        description="Amount for operation (token_a for enter, LP tokens for exit).",
    )
    use_max: Optional[bool] = Field(
        default=None,
        description="If true, derive amount automatically from current wallet balance for the selected pool token.",
    )

    @field_validator("action", mode="before")
    @classmethod
    def _norm_action(cls, value: Optional[str]) -> Optional[str]:
        return value.lower().replace(" ", "_") if isinstance(value, str) else value

    @field_validator("pool_id", mode="before")
    @classmethod
    def _norm_pool(cls, value: Optional[str]) -> Optional[str]:
        return value.upper().strip() if isinstance(value, str) else value

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
    return LiquidityConfig.validate_action(action)


def _validate_pool(pool_id: Optional[str]) -> Optional[str]:
    if pool_id is None:
        return None
    return LiquidityConfig.validate_pool(pool_id)


def _validate_amount(amount: Optional[Decimal], action: Optional[str]) -> Optional[Decimal]:
    if amount is None:
        return None
    if action is None:
        raise ValueError("Please specify the action before providing an amount.")

    min_amount = Decimal(LiquidityConfig.get_min_amount())
    if amount < min_amount:
        raise ValueError(f"Minimum amount is {min_amount}.")

    return amount


def _normalize_balance_map(raw_balances: Dict[str, Any]) -> Dict[str, Decimal]:
    balances: Dict[str, Decimal] = {}
    for symbol, raw in raw_balances.items():
        key = str(symbol or "").upper().strip()
        if not key:
            continue
        dec = _to_decimal(raw)
        if dec is None:
            continue
        balances[key] = balances.get(key, Decimal("0")) + dec
    return balances


def _parse_portfolio_payload(raw: Any) -> Dict[str, Any]:
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return {"error": "Failed to parse portfolio response"}
    if not isinstance(payload, dict):
        return {"error": "Invalid portfolio response"}
    return payload


def _fetch_portfolio_payload() -> Dict[str, Any]:
    try:
        raw = get_user_portfolio_tool.invoke({})  # type: ignore[attr-defined]
    except Exception:
        raw = get_user_portfolio_tool()  # fallback for direct call style
    return _parse_portfolio_payload(raw)


def _parse_base_balances_from_portfolio(payload: Dict[str, Any]) -> Dict[str, Decimal]:
    assets = payload.get("all_assets") or []
    if not isinstance(assets, list):
        assets = []

    base_balances: Dict[str, Decimal] = {}
    for item in assets:
        if not isinstance(item, dict):
            continue
        chain = str(item.get("chain") or "").lower()
        if chain != "base":
            continue
        symbol = str(item.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        bal_dec = _to_decimal(item.get("balance"))
        if bal_dec is None:
            continue
        base_balances[symbol] = base_balances.get(symbol, Decimal("0")) + bal_dec
    return base_balances


def _parse_base_balances_from_execution_portfolio(payload: Dict[str, Any]) -> Dict[str, Decimal]:
    balances: Dict[str, Decimal] = {}

    wallet_balances = payload.get("walletBalances")
    if isinstance(wallet_balances, dict):
        balances.update(_normalize_balance_map(wallet_balances))

    assets = payload.get("assets")
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            for token_key in ("tokenA", "tokenB"):
                token_info = asset.get(token_key)
                if not isinstance(token_info, dict):
                    continue
                symbol = str(token_info.get("symbol") or "").upper().strip()
                balance = _to_decimal(token_info.get("balance"))
                if not symbol or balance is None:
                    continue
                balances[symbol] = balances.get(symbol, Decimal("0")) + balance
    return balances


def _execution_api_candidates() -> List[str]:
    candidates: List[str] = []
    configured = os.getenv("YIELD_EXECUTION_API_BASES") or os.getenv("YIELD_EXECUTION_API_BASE") or ""
    for raw in configured.split(","):
        candidate = raw.strip().rstrip("/")
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    defaults = [
        "http://localhost:3011",
        "http://localhost:3010",
        "http://execution_service:3010",
    ]
    for candidate in defaults:
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _fetch_execution_base_balances(wallet_address: str | None) -> Optional[Dict[str, Decimal]]:
    if not wallet_address:
        return None
    key = wallet_address.lower()
    now = time.time()

    cached = _EXECUTION_BALANCE_CACHE.get(key)
    if cached and (now - cached[1]) < _EXECUTION_BALANCE_TTL_SECONDS:
        return cached[0]

    for base_url in _execution_api_candidates():
        url = f"{base_url}/staking/portfolio/{wallet_address}"
        try:
            response = requests.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
            if response.status_code >= 400:
                continue
            payload = response.json()
            if not isinstance(payload, dict):
                continue
            balances = _parse_base_balances_from_execution_portfolio(payload)
            if balances:
                _EXECUTION_BALANCE_CACHE[key] = (balances, now)
                _LAST_VALID_BALANCES[key] = (balances, now)
                return balances
        except Exception:
            continue

    last_valid = _LAST_VALID_BALANCES.get(key)
    if last_valid and (now - last_valid[1]) < _LAST_VALID_BALANCE_TTL_SECONDS:
        return last_valid[0]
    return None


def _fetch_execution_staked_lp_by_pool(wallet_address: str | None) -> Dict[str, Decimal]:
    if not wallet_address:
        return {}
    key = wallet_address.lower()
    now = time.time()
    cached = _EXECUTION_POSITION_CACHE.get(key)
    if cached and (now - cached[1]) < _EXECUTION_BALANCE_TTL_SECONDS:
        return cached[0]

    for base_url in _execution_api_candidates():
        url = f"{base_url}/staking/position/{wallet_address}"
        try:
            response = requests.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
            if response.status_code >= 400:
                continue
            payload = response.json()
            positions = payload if isinstance(payload, list) else []
            parsed: Dict[str, Decimal] = {}
            for position in positions:
                if not isinstance(position, dict):
                    continue
                pool_id = str(position.get("poolId") or position.get("pool_id") or "").strip().lower()
                if not pool_id:
                    continue
                staked = _to_decimal(position.get("stakedBalance") or position.get("staked_balance"))
                if staked is None:
                    continue
                parsed[pool_id] = staked
            if parsed:
                _EXECUTION_POSITION_CACHE[key] = (parsed, now)
                return parsed
        except Exception:
            continue
    return {}


def _derive_effective_balances(base_balances: Dict[str, Decimal]) -> Dict[str, Decimal]:
    effective = dict(base_balances)
    effective["WETH"] = effective.get("WETH", Decimal("0")) + effective.get("ETH", Decimal("0"))
    return effective


def _resolve_balances(payload: Dict[str, Any]) -> tuple[Dict[str, Decimal], str]:
    wallet_address = str(payload.get("wallet_address") or "").strip()
    execution_balances = _fetch_execution_base_balances(wallet_address)
    if execution_balances:
        return _derive_effective_balances(execution_balances), "execution_layer"

    fallback_balances = _parse_base_balances_from_portfolio(payload)
    if fallback_balances:
        if wallet_address:
            _LAST_VALID_BALANCES[wallet_address.lower()] = (fallback_balances, time.time())
        return _derive_effective_balances(fallback_balances), "portfolio_fallback"

    if wallet_address:
        last_valid = _LAST_VALID_BALANCES.get(wallet_address.lower())
        if last_valid and (time.time() - last_valid[1]) < _LAST_VALID_BALANCE_TTL_SECONDS:
            return _derive_effective_balances(last_valid[0]), "last_valid_cache"

    return {}, "unavailable"


def _resolve_max_amount(intent: LiquidityIntent, payload: Dict[str, Any]) -> Decimal:
    if not intent.action or not LiquidityConfig.action_needs_amount(intent.action):
        raise ValueError("Max amount can only be used for enter or exit actions.")

    token_a, _ = intent.get_pool_tokens()
    if not token_a or not intent.pool_id:
        raise ValueError("Please choose a pool before using max amount.")

    wallet_address = str(payload.get("wallet_address") or "").strip()
    if intent.action == "exit":
        staked_by_pool = _fetch_execution_staked_lp_by_pool(wallet_address)
        lp_balance = staked_by_pool.get(intent.pool_id.lower(), Decimal("0"))
        if lp_balance <= 0:
            raise ValueError("No staked LP balance found for this pool on Base.")
        min_amount = Decimal(LiquidityConfig.get_min_amount())
        if lp_balance < min_amount:
            raise ValueError(f"Available LP balance is below minimum amount ({min_amount}).")
        return lp_balance

    balances, source = _resolve_balances(payload)
    balance = balances.get(token_a, Decimal("0"))
    if balance <= 0:
        raise ValueError(f"No available {token_a} balance found on Base (source: {source}).")

    min_amount = Decimal(LiquidityConfig.get_min_amount())
    if balance < min_amount:
        raise ValueError(f"Available {token_a} balance is below minimum amount ({min_amount}).")
    return balance


# ---------- Output helpers ----------
def _store_liquidity_metadata(
    intent: LiquidityIntent,
    ask: Optional[str],
    done: bool,
    error: Optional[str],
    choices: Optional[List[str]] = None,
) -> Dict[str, Any]:
    intent.touch()
    missing = intent.missing_fields()
    next_field = missing[0] if missing else None
    token_a, token_b = intent.get_pool_tokens()
    legacy_action = LiquidityConfig.to_legacy_action(intent.action) if intent.action else None
    meta: Dict[str, Any] = {
        "event": "liquidity_intent_ready" if done else "liquidity_intent_pending",
        "status": "ready" if done else "collecting",
        "action": intent.action,
        "action_legacy": legacy_action,
        "pool_id": intent.pool_id,
        "amount": intent.amount_as_str(),
        "use_max": intent.use_max,
        "network": intent.network,
        "protocol": intent.protocol,
        "chain_id": intent.chain_id,
        "token_a": token_a,
        "token_b": token_b,
        "stable": intent.is_stable(),
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
    metadata.set_liquidity_agent(meta, intent.user_id, intent.conversation_id)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Liquidity metadata stored for user=%s conversation=%s done=%s error=%s",
            intent.user_id,
            intent.conversation_id,
            done,
            error,
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
    intent: LiquidityIntent,
    ask: Optional[str],
    choices: Optional[List[str]] = None,
    done: bool = False,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    meta = _store_liquidity_metadata(intent, ask, done, error, choices)

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
                "action_legacy",
                "pool_id",
                "amount",
                "use_max",
                "network",
                "protocol",
                "chain_id",
                "token_a",
                "token_b",
                "stable",
                "user_id",
                "conversation_id",
                "history",
            )
            if meta.get(key) is not None
        }
    return payload


# ---------- Core tool ----------
@tool("update_liquidity_intent", args_schema=UpdateLiquidityIntentInput)
def update_liquidity_intent_tool(
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    action: Optional[str] = None,
    pool_id: Optional[str] = None,
    amount: Optional[Decimal] = None,
    use_max: Optional[bool] = None,
):
    """Update the liquidity intent and surface the next question or final metadata.

    Call this tool whenever the user provides new liquidity/farming details. Supply only the
    fields that were mentioned in the latest message (leave the others as None)
    and keep calling it until the response event becomes 'liquidity_intent_ready'.

    Liquidity operations are done via Aerodrome Finance on Base:
    - enter: add liquidity and stake LP position
    - exit: unstake/remove LP position
    - claim: claim rewards
    """

    resolved_user, resolved_conversation = _resolve_session(user_id, conversation_id)
    intent = _load_intent(resolved_user, resolved_conversation)
    intent.user_id = resolved_user
    intent.conversation_id = resolved_conversation
    logger.info(
        "liquidity.tool=update_intent user=%s conversation=%s action_in=%s pool_in=%s amount_in=%s use_max=%s",
        resolved_user,
        resolved_conversation,
        action,
        pool_id,
        str(amount) if amount is not None else None,
        use_max,
    )

    try:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "update_liquidity_intent_tool input user=%s conversation=%s action=%s pool_id=%s amount=%s",
                user_id, conversation_id, action, pool_id, amount,
            )

        if action is not None:
            intent.action = _validate_action(action)
            if intent.action == "claim":
                intent.amount = None
                intent.use_max = False

        if intent.action is None:
            return _response(
                intent,
                "What would you like to do? Available actions: enter, exit, or claim.",
                LiquidityConfig.SUPPORTED_ACTIONS,
            )

        if pool_id is not None:
            intent.pool_id = _validate_pool(pool_id)

        if intent.pool_id is None:
            pools = LiquidityConfig.list_pools()
            pool_descriptions = []
            for pid in pools:
                pool = LiquidityConfig.get_pool(pid)
                if not pool:
                    continue
                display = pool.get("display", pid)
                pool_descriptions.append(f"{display} ({pool['description']})")
            return _response(
                intent,
                f"Which pool? Available: {', '.join(pool_descriptions)}",
                pools,
            )

        if LiquidityConfig.action_needs_amount(intent.action):
            if use_max is True:
                intent.use_max = True
                intent.amount = None
            elif use_max is False:
                intent.use_max = False

            if amount is not None:
                intent.amount = _validate_amount(amount, intent.action)
                intent.use_max = False

            if intent.use_max and intent.amount is None:
                payload = _fetch_portfolio_payload()
                if payload.get("error"):
                    raise ValueError(str(payload.get("error")))
                intent.amount = _resolve_max_amount(intent, payload)

            if intent.amount is None:
                token_a, _ = intent.get_pool_tokens()
                if intent.action == "enter":
                    return _response(intent, f"How much {token_a} do you want to deposit? You can also say 'max'.")
                else:
                    return _response(intent, "How many LP tokens do you want to exit? You can also say 'max'.")

    except ValueError as exc:
        message = str(exc)
        if logger.isEnabledFor(logging.INFO):
            logger.info(
                "Liquidity intent validation issue for user=%s conversation=%s: %s",
                intent.user_id, intent.conversation_id, message,
            )
        return _response(intent, "Please correct the input.", error=message)
    except Exception as exc:
        logger.exception(
            "Unexpected error updating liquidity intent for user=%s conversation=%s",
            intent.user_id, intent.conversation_id,
        )
        return _response(intent, "Please try again with the liquidity details.", error=str(exc))

    response = _response(intent, ask=None, done=True)
    logger.info(
        "liquidity.tool=update_intent event=%s status=%s action=%s pool_id=%s amount=%s use_max=%s",
        response.get("event"),
        (response.get("metadata") or {}).get("status"),
        intent.action,
        intent.pool_id,
        intent.amount_as_str(),
        intent.use_max,
    )
    return response


@tool("get_liquidity_info")
def get_liquidity_info_tool():
    """Get information about the liquidity/farming service (Aerodrome on Base).

    Returns details about the supported protocol, pools, and actions.
    """
    pools_info = {}
    for pid, pool in LiquidityConfig.POOLS.items():
        pools_info[pid] = {
            "display": pool.get("display", pid),
            "token_a": pool["token_a"],
            "token_b": pool["token_b"],
            "stable": pool["stable"],
            "description": pool["description"],
        }

    return {
        "protocol": LiquidityConfig.PROTOCOL,
        "network": LiquidityConfig.NETWORK,
        "chain_id": LiquidityConfig.CHAIN_ID,
        "supported_actions": LiquidityConfig.SUPPORTED_ACTIONS,
        "legacy_action_aliases": LiquidityConfig.LEGACY_ACTION_ALIASES,
        "pools": pools_info,
        "min_amount": LiquidityConfig.MIN_AMOUNT,
        "info": (
            "Aerodrome is the dominant DEX on Base. You can provide liquidity to pools "
            "and earn trading fees. Stake your LP tokens in Gauges to earn additional AERO rewards. "
            "Volatile pools (e.g. WETH-USDC) have higher potential returns but impermanent loss risk. "
            "Stable pools (e.g. USDC-USDbC) have lower returns but minimal impermanent loss."
        ),
    }


@tool("get_liquidity_pool_availability")
def get_liquidity_pool_availability_tool():
    """Compute which Aerodrome pools on Base can be used with the current wallet balances.

    Uses get_user_portfolio and filters only Base assets. For WETH requirements,
    ETH and WETH balances are both considered available (wrap step implied).
    """
    payload = _fetch_portfolio_payload()

    if payload.get("error"):
        logger.info(
            "liquidity.tool=pool_availability status=error error=%s",
            payload.get("error"),
        )
        return {
            "status": "error",
            "error": payload.get("error"),
            "eligible_pools": [],
            "ineligible_pools": [],
        }

    effective_balances, source = _resolve_balances(payload)

    eligible: List[Dict[str, Any]] = []
    ineligible: List[Dict[str, Any]] = []

    for pool_id, pool in LiquidityConfig.POOLS.items():
        token_a = pool["token_a"]
        token_b = pool["token_b"]
        bal_a = effective_balances.get(token_a, Decimal("0"))
        bal_b = effective_balances.get(token_b, Decimal("0"))

        details = {
            "pool_id": pool_id,
            "description": pool["description"],
            "token_a": token_a,
            "token_b": token_b,
            "stable": bool(pool.get("stable", False)),
            "balances": {
                token_a: str(bal_a.normalize() if bal_a != 0 else Decimal("0")),
                token_b: str(bal_b.normalize() if bal_b != 0 else Decimal("0")),
            },
        }

        if bal_a > 0 and bal_b > 0:
            eligible.append(details)
        else:
            missing = []
            if bal_a <= 0:
                missing.append(token_a)
            if bal_b <= 0:
                missing.append(token_b)
            details["missing_tokens"] = missing
            ineligible.append(details)

    response = {
        "status": "ok",
        "chain": "base",
        "balance_source": source,
        "wallet_address": payload.get("wallet_address"),
        "base_balances": {k: str(v.normalize() if v != 0 else Decimal("0")) for k, v in sorted(effective_balances.items())},
        "eligible_pools": eligible,
        "ineligible_pools": ineligible,
        "note": "ETH balance is counted as available for WETH-required pools (wrap step needed).",
    }
    logger.info(
        "liquidity.tool=pool_availability status=ok source=%s eligible=%d ineligible=%d",
        source,
        len(eligible),
        len(ineligible),
    )
    return response


def get_tools():
    return [update_liquidity_intent_tool, get_liquidity_info_tool, get_liquidity_pool_availability_tool]
