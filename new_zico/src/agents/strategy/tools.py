"""Tools for the strategy planning agent."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from src.agents.metadata import metadata

from .config import StrategyConfig, normalize_risk_tier, normalize_strategy_network
from .live_data import enrich_live_data
from .storage import StrategyStateRepository

_STORE = StrategyStateRepository.instance()
_REGISTRY_DIR = Path(__file__).resolve().parent
_REGISTRY_PATHS = {
    "avalanche": _REGISTRY_DIR / "strategy_registry.avalanche.json",
    "base": _REGISTRY_DIR / "strategy_registry.base.json",
}
_REGISTRY_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_PROTOCOL_CATEGORIES_CACHE: Dict[str, Dict[str, str]] = {}


def _load_registry(network: str) -> List[Dict[str, Any]]:
    normalized_network = normalize_strategy_network(network)
    cached = _REGISTRY_CACHE.get(normalized_network)
    if cached is not None:
        return cached
    path = _REGISTRY_PATHS.get(normalized_network) or _REGISTRY_PATHS["avalanche"]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    valid: List[Dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        protocols = entry.get("protocols") or []
        if not isinstance(protocols, list):
            continue
        if any(p not in StrategyConfig.ALLOWED_PROTOCOLS for p in protocols):
            continue
        if entry.get("risk_profile") not in StrategyConfig.STRATEGY_RISK_LEVELS:
            continue
        if not entry.get("enabled", True):
            continue
        valid.append(entry)
    _REGISTRY_CACHE[normalized_network] = valid
    return valid


def _protocol_categories(network: str) -> Dict[str, str]:
    normalized_network = normalize_strategy_network(network)
    cached = _PROTOCOL_CATEGORIES_CACHE.get(normalized_network)
    if cached is not None:
        return cached
    categories: Dict[str, str] = {}
    for entry in _load_registry(normalized_network):
        category = str(entry.get("category") or "").strip().lower()
        for protocol in entry.get("protocols") or []:
            if isinstance(protocol, str) and protocol and protocol not in categories:
                categories[protocol] = category
    _PROTOCOL_CATEGORIES_CACHE[normalized_network] = categories
    return categories


def _risk_rank(risk: str | None) -> int:
    rank = {"low": 1, "medium": 2, "high": 3, "very_high": 4}
    return rank.get((risk or "").lower(), 2)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass
class StrategyIntent:
    user_id: str
    conversation_id: str
    stage: str = "profiling"
    risk_tier: Optional[str] = None
    overrides: Dict[str, Any] = field(default_factory=dict)
    selected_strategies: List[str] = field(default_factory=list)
    comparison_set: List[str] = field(default_factory=list)
    recommended_allocations: List[Dict[str, Any]] = field(default_factory=list)
    simulation_results: Dict[str, Any] = field(default_factory=dict)
    high_risk_opt_in: bool = False
    confirmed: bool = False
    updated_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "stage": self.stage,
            "risk_tier": self.risk_tier,
            "overrides": dict(self.overrides),
            "selected_strategies": list(self.selected_strategies),
            "comparison_set": list(self.comparison_set),
            "recommended_allocations": list(self.recommended_allocations),
            "simulation_results": dict(self.simulation_results),
            "high_risk_opt_in": self.high_risk_opt_in,
            "confirmed": self.confirmed,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "StrategyIntent":
        intent = cls(
            user_id=payload.get("user_id") or "",
            conversation_id=payload.get("conversation_id") or "",
            stage=payload.get("stage") or "profiling",
        )
        intent.risk_tier = payload.get("risk_tier")
        intent.overrides = dict(payload.get("overrides") or {})
        intent.selected_strategies = list(payload.get("selected_strategies") or [])
        intent.comparison_set = list(payload.get("comparison_set") or [])
        intent.recommended_allocations = list(payload.get("recommended_allocations") or [])
        intent.simulation_results = dict(payload.get("simulation_results") or {})
        intent.high_risk_opt_in = bool(payload.get("high_risk_opt_in", False))
        intent.confirmed = bool(payload.get("confirmed", False))
        intent.updated_at = float(payload.get("updated_at") or time.time())
        return intent

    def missing_fields(self) -> List[str]:
        if self.stage == "ready":
            return []
        missing: List[str] = []
        if self.stage == "profiling":
            if not self.risk_tier:
                missing.append("risk_tier")
        elif self.stage == "discovery":
            if not self.selected_strategies:
                missing.append("strategy_selection")
        elif self.stage == "recommendation":
            if not self.recommended_allocations:
                missing.append("allocations")
            if not self.simulation_results:
                missing.append("simulation")
        elif self.stage == "comparison":
            if not self.comparison_set:
                missing.append("comparison_set")
        elif self.stage == "confirmation":
            if not self.confirmed:
                missing.append("confirmation")
        return missing

    def next_field(self) -> Optional[str]:
        missing = self.missing_fields()
        return missing[0] if missing else None


_CURRENT_SESSION: ContextVar[tuple[str, str]] = ContextVar("_current_strategy_session", default=("", ""))


def set_current_strategy_session(user_id: Optional[str], conversation_id: Optional[str]) -> None:
    resolved_user = (user_id or "").strip()
    resolved_conversation = (conversation_id or "").strip()
    if not resolved_user:
        raise ValueError("strategy_agent requires 'user_id' to identify the session.")
    if not resolved_conversation:
        raise ValueError("strategy_agent requires 'conversation_id' to identify the session.")
    _CURRENT_SESSION.set((resolved_user, resolved_conversation))


@contextmanager
def strategy_session(user_id: Optional[str], conversation_id: Optional[str]):
    set_current_strategy_session(user_id, conversation_id)
    try:
        yield
    finally:
        clear_current_strategy_session()


def clear_current_strategy_session() -> None:
    _CURRENT_SESSION.set(("", ""))


def _resolve_session(user_id: Optional[str], conversation_id: Optional[str]) -> tuple[str, str]:
    active_user, active_conversation = _CURRENT_SESSION.get()
    resolved_user = (user_id or active_user or "").strip()
    resolved_conversation = (conversation_id or active_conversation or "").strip()
    if not resolved_user:
        raise ValueError("user_id is required for strategy operations.")
    if not resolved_conversation:
        raise ValueError("conversation_id is required for strategy operations.")
    return resolved_user, resolved_conversation


def _load_intent(user_id: str, conversation_id: str) -> StrategyIntent:
    stored = _STORE.load_intent(user_id, conversation_id)
    if stored:
        intent = StrategyIntent.from_dict(stored)
        intent.user_id = user_id
        intent.conversation_id = conversation_id
        return intent
    return StrategyIntent(user_id=user_id, conversation_id=conversation_id)


def _resolve_strategy_network(intent: StrategyIntent, explicit: Optional[str] = None) -> str:
    network = normalize_strategy_network(explicit or str(intent.overrides.get("network") or ""))
    intent.overrides["network"] = network
    return network


def _score_strategy(
    strategy: Dict[str, Any],
    intent: StrategyIntent,
    network: str,
) -> tuple[float, List[str], List[str], Dict[str, Any]]:
    reasons: List[str] = []
    exclusions: List[str] = []

    preferred_risk = intent.risk_tier or "medium"
    strategy_risk = strategy.get("risk_profile", "medium")

    distance = abs(_risk_rank(preferred_risk) - _risk_rank(strategy_risk))
    risk_score = _clamp(1.0 - 0.22 * distance)
    if distance == 0:
        reasons.append(f"Risk profile match ({strategy_risk}).")
    else:
        reasons.append(f"Risk profile partial match ({strategy_risk} vs {preferred_risk}).")

    capital = intent.overrides.get("capital_usd")
    cap_req = strategy.get("capital_requirements") or {}
    min_cap = cap_req.get("min_usd")
    if capital is None or min_cap is None:
        capital_score = 0.75
    elif float(capital) >= float(min_cap):
        capital_score = 1.0
        reasons.append("Capital requirement satisfied.")
    else:
        capital_score = 0.2
        exclusions.append(f"Capital below minimum ({capital} < {min_cap}).")

    live = enrich_live_data(strategy.get("category", ""), strategy.get("protocols", []), network=network)
    tvl = live.get("tvl")
    liquidity_score = 0.7 if tvl is None else _clamp(min(float(tvl) / 1_000_000_000, 1.0))
    if live.get("freshness") == "stale":
        liquidity_score *= 0.8

    penalty = 0.0
    for protocol in strategy.get("protocols") or []:
        penalty += StrategyConfig.PROTOCOL_RISK_PENALTY.get(protocol, 0.08)
    penalty = min(penalty, 0.35)

    portfolio_boost = 0.0
    allocation = intent.overrides.get("portfolio_allocation")
    if isinstance(allocation, dict):
        stable = float(allocation.get("stablecoins_pct") or 0)
        alt = float(allocation.get("altcoins_pct") or 0)
        if strategy.get("category") == "rwa" and alt > 45:
            portfolio_boost += 0.08
            reasons.append("Improves diversification versus altcoin-heavy wallet.")
        if strategy.get("category") == "lp" and stable > 70:
            portfolio_boost += 0.05
            reasons.append("Adds return opportunities to stable-heavy wallet.")

    score = _clamp((0.35 * risk_score) + (0.25 * capital_score) + (0.25 * liquidity_score) + (0.15 * (1 - penalty)) + portfolio_boost)

    return score, reasons, exclusions, live


def _build_next_action(meta: Dict[str, Any]) -> Dict[str, Any]:
    if meta.get("status") == "ready":
        return {"type": "complete", "prompt": None, "field": None, "choices": []}
    return {
        "type": "collect_field",
        "prompt": meta.get("pending_question"),
        "field": meta.get("next_field"),
        "choices": meta.get("choices") or [],
    }


def _build_prompt(field: Optional[str]) -> Optional[str]:
    prompts = {
        "risk_tier": "What is your risk preference (low, medium, high)?",
        "strategy_selection": "Select one or more strategies to evaluate in detail.",
        "allocations": "What allocation split do you want across shortlisted strategies?",
        "simulation": "Should I run simulations for 30, 90, and 180 days with stress scenarios?",
        "comparison_set": "Which strategies should be compared side-by-side?",
        "confirmation": "Ready to confirm this strategy plan and prepare handoff payloads?",
    }
    return prompts.get(field)


def _build_choices(field: Optional[str], intent: StrategyIntent) -> List[str]:
    if field == "risk_tier":
        return ["low", "medium", "high"]
    if field == "simulation":
        return ["yes", "no"]
    if field == "confirmation":
        return ["yes", "no"]
    if field in {"strategy_selection", "comparison_set"}:
        return list(intent.selected_strategies)[: StrategyConfig.MAX_TOP_K]
    return []


def _workflow_payload(intent: StrategyIntent) -> Dict[str, Any]:
    selected = intent.selected_strategies[0] if intent.selected_strategies else None
    network = normalize_strategy_network(str(intent.overrides.get("network") or ""))
    return {
        "workflow_type": StrategyConfig.WORKFLOW_TYPE,
        "network": network,
        "strategy_id": selected,
        "risk_tier": intent.risk_tier,
        "overrides": dict(intent.overrides),
        "allocations": list(intent.recommended_allocations),
        "simulation": dict(intent.simulation_results),
        "live_data_freshness": intent.simulation_results.get("freshness") if isinstance(intent.simulation_results, dict) else None,
        "handoff": None,
    }


def _summary(intent: StrategyIntent, error: Optional[str] = None) -> Dict[str, Any]:
    selected = intent.selected_strategies[0] if intent.selected_strategies else None
    network = normalize_strategy_network(str(intent.overrides.get("network") or ""))
    summary = {
        "summary": f"Strategy plan ready for {selected or 'selection'} ({intent.risk_tier or 'medium'} risk).",
        "workflow_type": StrategyConfig.WORKFLOW_TYPE,
        "network": network,
        "strategy_id": selected,
        "risk_tier": intent.risk_tier,
        "overrides": dict(intent.overrides),
        "allocations": list(intent.recommended_allocations),
        "simulation": dict(intent.simulation_results),
    }
    if error:
        summary["error"] = error
    return summary


def _store_metadata(
    intent: StrategyIntent,
    ask: Optional[str],
    choices: Optional[List[str]],
    done: bool,
    error: Optional[str],
    event: str,
) -> Dict[str, Any]:
    intent.touch()
    missing = intent.missing_fields()
    next_field = intent.next_field()
    meta = {
        "event": event,
        "status": "ready" if done else intent.stage,
        "stage": intent.stage,
        "missing_fields": missing,
        "next_field": next_field,
        "pending_question": ask,
        "choices": list(choices or []),
        "error": error,
        "user_id": intent.user_id,
        "conversation_id": intent.conversation_id,
    }
    meta.update(intent.to_dict())
    summary = _summary(intent, error=error) if done else None
    history = _STORE.persist_intent(intent.user_id, intent.conversation_id, intent.to_dict(), meta, done=done, summary=summary)
    if history:
        meta["history"] = history
    metadata.set_strategy_agent(meta, intent.user_id, intent.conversation_id)
    return meta


def _response(
    intent: StrategyIntent,
    *,
    ask: Optional[str],
    choices: Optional[List[str]],
    done: bool,
    error: Optional[str],
    event: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta = _store_metadata(intent, ask, choices, done, error, event)
    payload: Dict[str, Any] = {
        "event": event,
        "intent": intent.to_dict(),
        "ask": ask,
        "choices": choices or [],
        "error": error,
        "next_action": _build_next_action(meta),
        "stage": meta.get("stage"),
        "status": meta.get("status"),
        "history": meta.get("history", []),
    }
    if done:
        payload["metadata"] = _workflow_payload(intent)
    if extra:
        payload.update(extra)
    return payload


class FetchStrategyCandidatesInput(BaseModel):
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    network: Optional[str] = None
    risk_tier: Optional[str] = None
    top_k: int = Field(default=StrategyConfig.DEFAULT_TOP_K, ge=1, le=StrategyConfig.MAX_TOP_K)
    high_risk_opt_in: Optional[bool] = None
    rwa_only: Optional[bool] = None
    stablecoin_only: Optional[bool] = None
    exclude_protocols: Optional[List[str]] = None
    capital_usd: Optional[float] = Field(default=None, ge=0)
    max_drawdown_pct: Optional[float] = Field(default=None, ge=0, le=100)
    max_leverage: Optional[float] = Field(default=None, ge=0)
    time_horizon_days: Optional[int] = Field(default=None, ge=1)
    portfolio_allocation: Optional[Dict[str, Any]] = None

    @field_validator("risk_tier", mode="before")
    @classmethod
    def _normalize_risk(cls, value: Any) -> Any:
        if value is None:
            return None
        normalized = normalize_risk_tier(str(value))
        return normalized or value


class UpdateStrategyIntentInput(BaseModel):
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    network: Optional[str] = None
    stage: Optional[str] = None
    risk_tier: Optional[str] = None
    overrides: Optional[Dict[str, Any]] = None
    selected_strategies: Optional[List[str]] = None
    comparison_set: Optional[List[str]] = None
    recommended_allocations: Optional[List[Dict[str, Any]]] = None
    high_risk_opt_in: Optional[bool] = None
    confirm: Optional[bool] = None


class SimulateStrategyOutcomesInput(BaseModel):
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    network: Optional[str] = None
    strategy_ids: Optional[List[str]] = None
    horizons_days: Optional[List[int]] = None


class PrepareStrategyHandoffInput(BaseModel):
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    network: Optional[str] = None
    strategy_id: Optional[str] = None


class ResetStrategyIntentInput(BaseModel):
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None


class CompareProtocolLiveDataInput(BaseModel):
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    network: Optional[str] = None
    protocols: List[str] = Field(default_factory=list)


@tool("fetch_strategy_candidates", args_schema=FetchStrategyCandidatesInput)
def fetch_strategy_candidates_tool(**kwargs) -> Dict[str, Any]:
    """Fetch ranked strategy candidates according to user constraints."""

    user_id, conversation_id = _resolve_session(kwargs.get("user_id"), kwargs.get("conversation_id"))
    intent = _load_intent(user_id, conversation_id)
    network = _resolve_strategy_network(intent, kwargs.get("network"))
    registry = _load_registry(network)

    risk_tier = normalize_risk_tier(kwargs.get("risk_tier"))
    if risk_tier:
        intent.risk_tier = risk_tier

    if kwargs.get("high_risk_opt_in") is not None:
        intent.high_risk_opt_in = bool(kwargs["high_risk_opt_in"])

    for key in (
        "rwa_only",
        "stablecoin_only",
        "exclude_protocols",
        "capital_usd",
        "max_drawdown_pct",
        "max_leverage",
        "time_horizon_days",
        "portfolio_allocation",
    ):
        if kwargs.get(key) is not None:
            intent.overrides[key] = kwargs[key]

    exclude_protocols = set(intent.overrides.get("exclude_protocols") or [])
    rwa_only = bool(intent.overrides.get("rwa_only", False))
    stable_only = bool(intent.overrides.get("stablecoin_only", False))

    candidates: List[Dict[str, Any]] = []
    blocked: List[str] = []

    for strategy in registry:
        risk_profile = strategy.get("risk_profile")
        if not intent.high_risk_opt_in and risk_profile in {"high", "very_high"}:
            blocked.append(f"{strategy.get('strategy_id')}: high-risk requires explicit opt-in")
            continue
        if rwa_only and strategy.get("category") != "rwa":
            continue
        if stable_only:
            cap_asset = str((strategy.get("capital_requirements") or {}).get("asset", "")).upper()
            if cap_asset not in {"USDC", "USDT", "DAI"}:
                continue
        protocols = set(strategy.get("protocols") or [])
        if exclude_protocols and protocols.intersection(exclude_protocols):
            blocked.append(f"{strategy.get('strategy_id')}: excluded protocol overlap")
            continue

        score, reasons, exclusions, live = _score_strategy(strategy, intent, network)
        candidates.append(
            {
                "strategy_id": strategy.get("strategy_id"),
                "name": strategy.get("name"),
                "category": strategy.get("category"),
                "risk_profile": risk_profile,
                "protocols": strategy.get("protocols"),
                "score": round(score, 4),
                "fit_rationale": reasons,
                "exclusions": exclusions,
                "mechanism": strategy.get("mechanism"),
                "yield_source": strategy.get("yield_source"),
                "risks": strategy.get("risks"),
                "live": live,
            }
        )

    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    top_k = int(kwargs.get("top_k") or StrategyConfig.DEFAULT_TOP_K)
    selected = [c["strategy_id"] for c in candidates[:top_k]]
    intent.selected_strategies = selected

    if intent.risk_tier and intent.stage == "profiling":
        intent.stage = "discovery"
    if intent.selected_strategies and intent.stage == "discovery":
        intent.stage = "recommendation"

    ask = _build_prompt(intent.next_field())
    choices = _build_choices(intent.next_field(), intent)
    event = "strategy_recommendations_ready" if selected else "strategy_intent_collecting"

    return _response(
        intent,
        ask=ask,
        choices=choices,
        done=False,
        error=None,
        event=event,
        extra={
            "suggestions": candidates[:top_k],
            "blocked": blocked,
            "high_risk_opt_in": intent.high_risk_opt_in,
            "network": network,
        },
    )


@tool("update_strategy_intent", args_schema=UpdateStrategyIntentInput)
def update_strategy_intent_tool(**kwargs) -> Dict[str, Any]:
    """Update strategy planning intent fields."""

    user_id, conversation_id = _resolve_session(kwargs.get("user_id"), kwargs.get("conversation_id"))
    intent = _load_intent(user_id, conversation_id)
    _resolve_strategy_network(intent, kwargs.get("network"))

    stage = kwargs.get("stage")
    if stage:
        stage = str(stage).strip().lower()
        if stage in StrategyConfig.STAGES:
            intent.stage = stage

    risk_tier = normalize_risk_tier(kwargs.get("risk_tier"))
    if risk_tier:
        intent.risk_tier = risk_tier

    if kwargs.get("overrides"):
        intent.overrides.update(dict(kwargs.get("overrides") or {}))

    for key in ("selected_strategies", "comparison_set", "recommended_allocations"):
        value = kwargs.get(key)
        if value is not None:
            setattr(intent, key, list(value))

    if kwargs.get("high_risk_opt_in") is not None:
        intent.high_risk_opt_in = bool(kwargs["high_risk_opt_in"])

    if kwargs.get("confirm") is not None:
        intent.confirmed = bool(kwargs["confirm"])

    if intent.stage == "profiling" and intent.risk_tier:
        intent.stage = "discovery"
    if intent.stage == "discovery" and intent.selected_strategies:
        intent.stage = "recommendation"
    if intent.stage == "recommendation" and intent.recommended_allocations and intent.simulation_results:
        intent.stage = "comparison"
    if intent.stage == "comparison" and intent.comparison_set:
        intent.stage = "confirmation"
    if intent.stage == "confirmation" and intent.confirmed:
        intent.stage = "ready"

    done = intent.stage == "ready"
    ask = None if done else _build_prompt(intent.next_field())
    choices = [] if done else _build_choices(intent.next_field(), intent)

    return _response(
        intent,
        ask=ask,
        choices=choices,
        done=done,
        error=None,
        event="strategy_intent_ready" if done else "strategy_intent_collecting",
    )


@tool("simulate_strategy_outcomes", args_schema=SimulateStrategyOutcomesInput)
def simulate_strategy_outcomes_tool(**kwargs) -> Dict[str, Any]:
    """Simulate strategy outcomes for 30/90/180d horizons with stress scenarios."""

    user_id, conversation_id = _resolve_session(kwargs.get("user_id"), kwargs.get("conversation_id"))
    intent = _load_intent(user_id, conversation_id)
    network = _resolve_strategy_network(intent, kwargs.get("network"))
    registry = _load_registry(network)

    requested = list(kwargs.get("strategy_ids") or intent.selected_strategies)
    if not requested:
        return _response(
            intent,
            ask="Select strategies before simulation.",
            choices=[],
            done=False,
            error="No strategies selected for simulation.",
            event="strategy_intent_collecting",
        )

    horizons = kwargs.get("horizons_days") or StrategyConfig.DEFAULT_HORIZONS_DAYS
    horizons = [int(h) for h in horizons if int(h) > 0]

    capital = float(intent.overrides.get("capital_usd") or 1000)
    results: Dict[str, Any] = {}
    freshness = "fresh"
    warnings: List[str] = []

    by_id = {s["strategy_id"]: s for s in registry}

    for strategy_id in requested:
        strategy = by_id.get(strategy_id)
        if not strategy:
            continue

        assumptions = strategy.get("simulation_assumptions") or {}
        base_apy = float(assumptions.get("base_apy") or 0.1)
        live = enrich_live_data(strategy.get("category", ""), strategy.get("protocols", []), network=network)
        live_apy = live.get("apy")
        if isinstance(live_apy, (float, int)):
            base_apy = float(live_apy)

        if live.get("freshness") == "stale":
            freshness = "stale"
            if live.get("warning"):
                warnings.append(str(live.get("warning")))

        conservative = max(base_apy * 0.75, 0)
        aggressive = max(base_apy * 1.25, conservative)

        horizon_payload: Dict[str, Any] = {}
        for days in horizons:
            factor = days / 365.0
            horizon_payload[str(days)] = {
                "conservative": round(capital * conservative * factor, 2),
                "base": round(capital * base_apy * factor, 2),
                "aggressive": round(capital * aggressive * factor, 2),
            }

        category = strategy.get("category") or "structured"
        stress_key = StrategyConfig.CATEGORY_STRESS_SCENARIOS.get(category, "volatility_shock")
        volatility = float(assumptions.get("volatility") or 0.12)
        stress = {
            "scenario": stress_key,
            "drawdown_pct": round(min(volatility * 100 * 1.5, 85), 2),
            "notes": f"Stress scenario for category '{category}'.",
        }

        results[strategy_id] = {
            "assumptions": {
                "capital_usd": capital,
                "base_apy": round(base_apy, 4),
                "volatility": round(volatility, 4),
            },
            "horizons": horizon_payload,
            "stress": stress,
            "live_data": live,
        }

    intent.simulation_results = {
        "network": network,
        "horizons": horizons,
        "by_strategy": results,
        "freshness": freshness,
        "warnings": sorted(set(warnings)),
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if intent.stage == "recommendation" and intent.recommended_allocations:
        intent.stage = "comparison"

    return _response(
        intent,
        ask=_build_prompt(intent.next_field()),
        choices=_build_choices(intent.next_field(), intent),
        done=False,
        error=None,
        event="strategy_comparison_ready",
        extra={"simulation": intent.simulation_results},
    )


@tool("prepare_strategy_handoff", args_schema=PrepareStrategyHandoffInput)
def prepare_strategy_handoff_tool(**kwargs) -> Dict[str, Any]:
    """Prepare handoff payloads to downstream execution-specialized agents."""

    user_id, conversation_id = _resolve_session(kwargs.get("user_id"), kwargs.get("conversation_id"))
    intent = _load_intent(user_id, conversation_id)
    network = _resolve_strategy_network(intent, kwargs.get("network"))
    registry = _load_registry(network)

    strategy_id = kwargs.get("strategy_id")
    if not strategy_id:
        strategy_id = intent.selected_strategies[0] if intent.selected_strategies else None

    by_id = {s["strategy_id"]: s for s in registry}
    strategy = by_id.get(strategy_id) if strategy_id else None

    if not strategy:
        return _response(
            intent,
            ask="Select a strategy before preparing handoff.",
            choices=intent.selected_strategies,
            done=False,
            error="Unknown strategy_id for handoff.",
            event="strategy_intent_collecting",
        )

    mapping = strategy.get("handoff_mapping", "none")
    handoff_target = {
        "lending": "lending_agent",
        "staking": "staking_agent",
        "dca": "dca_agent",
        "swap": "swap_agent",
        "none": None,
    }.get(mapping, None)

    unresolved: List[str] = []
    prefilled: Dict[str, Any] = {
        "strategy_id": strategy.get("strategy_id"),
        "strategy_name": strategy.get("name"),
        "risk_profile": strategy.get("risk_profile"),
        "protocols": strategy.get("protocols"),
    }

    cap_req = strategy.get("capital_requirements") or {}
    if mapping == "lending":
        prefilled.update(
            {
                "action": "supply",
                "network": network,
                "asset": cap_req.get("asset") or "USDC",
                "amount": intent.overrides.get("capital_usd"),
            }
        )
        if prefilled.get("amount") is None:
            unresolved.append("amount")
    elif mapping == "staking":
        prefilled.update({"action": "stake", "amount": intent.overrides.get("capital_usd")})
        if prefilled.get("amount") is None:
            unresolved.append("amount")
    elif mapping == "swap":
        prefilled.update({"network": network, "amount": intent.overrides.get("capital_usd")})
        unresolved.extend(["from_token", "to_token"])

    handoff = {
        "target_agent": handoff_target,
        "prefilled_fields": prefilled,
        "unresolved_fields": unresolved,
        "risk_disclaimers": list(strategy.get("risks") or []),
    }

    intent.confirmed = True
    intent.stage = "ready"

    response = _response(
        intent,
        ask=None,
        choices=[],
        done=True,
        error=None,
        event="strategy_intent_ready",
        extra={"handoff": handoff},
    )
    if response.get("metadata"):
        response["metadata"]["handoff"] = handoff
    return response


@tool("compare_protocol_live_data", args_schema=CompareProtocolLiveDataInput)
def compare_protocol_live_data_tool(**kwargs) -> Dict[str, Any]:
    """Compare current APY/live-data snapshots across provided protocols."""

    user_id, conversation_id = _resolve_session(kwargs.get("user_id"), kwargs.get("conversation_id"))
    intent = _load_intent(user_id, conversation_id)
    network = _resolve_strategy_network(intent, kwargs.get("network"))
    protocol_categories = _protocol_categories(network)

    requested = [p for p in list(kwargs.get("protocols") or []) if isinstance(p, str) and p.strip()]
    if not requested:
        return _response(
            intent,
            ask="Tell me which protocols to compare.",
            choices=sorted(StrategyConfig.ALLOWED_PROTOCOLS),
            done=False,
            error="No protocols provided.",
            event="strategy_intent_collecting",
        )

    rows: List[Dict[str, Any]] = []
    for protocol in requested:
        normalized = next((p for p in StrategyConfig.ALLOWED_PROTOCOLS if p.lower() == protocol.lower().strip()), protocol)
        category = protocol_categories.get(normalized, "lending")
        live = enrich_live_data(category, [normalized], network=network)
        rows.append(
            {
                "protocol": normalized,
                "category": category,
                "apy": live.get("apy"),
                "source": live.get("source"),
                "freshness": live.get("freshness"),
                "as_of": live.get("as_of"),
                "confidence": live.get("confidence"),
                "warning": live.get("warning"),
            }
        )

    rows_sorted = sorted(rows, key=lambda r: float(r.get("apy") or -1), reverse=True)
    best = rows_sorted[0] if rows_sorted else None
    return _response(
        intent,
        ask=None,
        choices=[],
        done=False,
        error=None,
        event="strategy_protocol_comparison_ready",
        extra={
            "network": network,
            "comparison": rows_sorted,
            "best_protocol": best.get("protocol") if best else None,
            "best_apy": best.get("apy") if best else None,
        },
    )


@tool("reset_strategy_intent", args_schema=ResetStrategyIntentInput)
def reset_strategy_intent_tool(**kwargs) -> Dict[str, Any]:
    """Reset the strategy planning session."""

    user_id, conversation_id = _resolve_session(kwargs.get("user_id"), kwargs.get("conversation_id"))
    _STORE.clear_intent(user_id, conversation_id)
    metadata.clear_strategy_agent(user_id, conversation_id)
    intent = StrategyIntent(user_id=user_id, conversation_id=conversation_id)
    return _response(
        intent,
        ask="Let's define your risk profile first (low, medium, high).",
        choices=["low", "medium", "high"],
        done=False,
        error=None,
        event="strategy_intent_collecting",
    )


def get_tools() -> list:
    return [
        fetch_strategy_candidates_tool,
        update_strategy_intent_tool,
        simulate_strategy_outcomes_tool,
        compare_protocol_live_data_tool,
        prepare_strategy_handoff_tool,
        reset_strategy_intent_tool,
    ]
