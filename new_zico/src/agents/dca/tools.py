"""DCA tools that orchestrate consulting, recommendation, and confirmation flows."""

from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from src.agents.metadata import metadata

from .storage import DcaStateRepository
from .strategy import get_strategy_retriever

_STORE = DcaStateRepository.instance()


def _decimal_as_str(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.normalize()
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


STAGES: Sequence[str] = ("consulting", "recommendation", "confirmation", "ready")


@dataclass
class DcaIntent:
    user_id: str
    conversation_id: str
    stage: str = "consulting"
    strategy_id: Optional[str] = None
    strategy_version: Optional[str] = None
    strategy_name: Optional[str] = None
    strategy_summary: Optional[str] = None
    rag_confidence: Optional[float] = None
    strategy_defaults: Dict[str, Any] = field(default_factory=dict)
    guardrails: List[str] = field(default_factory=list)
    compliance_notes: List[str] = field(default_factory=list)
    from_token: Optional[str] = None
    to_token: Optional[str] = None
    cadence: Optional[str] = None
    start_on: Optional[str] = None
    iterations: Optional[int] = None
    end_on: Optional[str] = None
    total_amount: Optional[Decimal] = None
    per_cycle_amount: Optional[Decimal] = None
    venue: Optional[str] = None
    slippage_bps: Optional[int] = None
    stop_conditions: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    timezone: Optional[str] = None
    confirmed: bool = False
    updated_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.updated_at = time.time()

    def advance_stage(self, stage: str | None) -> None:
        if not stage or stage == self.stage:
            return
        if stage not in STAGES:
            raise ValueError(f"Unsupported stage '{stage}'. Choose from {', '.join(STAGES)}.")
        current_index = STAGES.index(self.stage if self.stage in STAGES else "consulting")
        target_index = STAGES.index(stage)
        if target_index < current_index:
            self.stage = stage
            return
        if stage == "ready" and not self.confirmed:
            raise ValueError("Cannot mark stage as ready before confirmation.")
        self.stage = stage

    def missing_fields(self) -> List[str]:
        if self.stage == "ready":
            return []
        missing: List[str] = []
        if self.stage == "consulting":
            if not self.strategy_id:
                missing.append("strategy_id")
            if not self.from_token:
                missing.append("from_token")
            if not self.to_token:
                missing.append("to_token")
        elif self.stage == "recommendation":
            if not self.cadence:
                missing.append("cadence")
            if not self.start_on:
                missing.append("start_on")
            if self.iterations is None and not self.end_on:
                missing.append("iterations_or_end_on")
            if self.total_amount is None and self.per_cycle_amount is None:
                missing.append("total_or_per_cycle_amount")
            if not self.venue:
                missing.append("venue")
            if self.slippage_bps is None:
                missing.append("slippage_bps")
        elif self.stage == "confirmation":
            if not self.confirmed:
                missing.append("confirmation")
        return missing

    def next_field(self) -> Optional[str]:
        missing = self.missing_fields()
        return missing[0] if missing else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "stage": self.stage,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "strategy_name": self.strategy_name,
            "strategy_summary": self.strategy_summary,
            "rag_confidence": self.rag_confidence,
            "strategy_defaults": self.strategy_defaults,
            "guardrails": list(self.guardrails),
            "compliance_notes": list(self.compliance_notes),
            "from_token": self.from_token,
            "to_token": self.to_token,
            "cadence": self.cadence,
            "start_on": self.start_on,
            "iterations": self.iterations,
            "end_on": self.end_on,
            "total_amount": _decimal_as_str(self.total_amount),
            "per_cycle_amount": _decimal_as_str(self.per_cycle_amount),
            "venue": self.venue,
            "slippage_bps": self.slippage_bps,
            "stop_conditions": list(self.stop_conditions),
            "notes": self.notes,
            "timezone": self.timezone,
            "confirmed": self.confirmed,
            "updated_at": self.updated_at,
        }

    def to_public(self) -> Dict[str, Any]:
        data = self.to_dict()
        data["updated_at"] = datetime_from_timestamp(self.updated_at)
        return data

    def to_summary(self, error: Optional[str] = None) -> Dict[str, Any]:
        summary = {
            "summary": (
                f"DCA from {self.from_token} to {self.to_token} "
                f"({self.cadence}) starting {self.start_on}"
            ),
            "workflow_type": "dca_swap",
            "cadence": {"interval": self.cadence, "start_on": self.start_on, "iterations": self.iterations, "end_on": self.end_on},
            "tokens": {"from": self.from_token, "to": self.to_token},
            "amounts": {
                "total": _decimal_as_str(self.total_amount),
                "per_cycle": _decimal_as_str(self.per_cycle_amount),
            },
            "notes": self.notes,
            "strategy": {
                "strategy_id": self.strategy_id,
                "strategy_version": self.strategy_version,
                "confidence": self.rag_confidence,
            },
            "venue": self.venue,
            "slippage_bps": self.slippage_bps,
            "stop_conditions": list(self.stop_conditions),
        }
        if error:
            summary["error"] = error
        return summary

    def to_workflow_payload(self) -> Dict[str, Any]:
        return {
            "workflow_type": "dca_swap",
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "tokens": {"from": self.from_token, "to": self.to_token},
            "cadence": {
                "interval": self.cadence,
                "start_on": self.start_on,
                "iterations": self.iterations,
                "end_on": self.end_on,
            },
            "amounts": {
                "total": _decimal_as_str(self.total_amount),
                "per_cycle": _decimal_as_str(self.per_cycle_amount),
            },
            "venue": self.venue,
            "slippage_bps": self.slippage_bps,
            "stop_conditions": list(self.stop_conditions),
            "notes": self.notes,
            "strategy_defaults": self.strategy_defaults,
            "guardrails": list(self.guardrails),
            "compliance_notes": list(self.compliance_notes),
            "rag_confidence": self.rag_confidence,
            "metadata": {
                "timezone": self.timezone,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DcaIntent":
        intent = cls(
            user_id=data.get("user_id", ""),
            conversation_id=data.get("conversation_id", ""),
            stage=data.get("stage", "consulting"),
        )
        intent.strategy_id = data.get("strategy_id")
        intent.strategy_version = data.get("strategy_version")
        intent.strategy_name = data.get("strategy_name")
        intent.strategy_summary = data.get("strategy_summary")
        intent.rag_confidence = data.get("rag_confidence")
        intent.strategy_defaults = data.get("strategy_defaults") or {}
        intent.guardrails = list(data.get("guardrails") or [])
        intent.compliance_notes = list(data.get("compliance_notes") or [])
        intent.from_token = data.get("from_token")
        intent.to_token = data.get("to_token")
        intent.cadence = data.get("cadence")
        intent.start_on = data.get("start_on")
        intent.iterations = data.get("iterations")
        intent.end_on = data.get("end_on")
        intent.total_amount = _to_decimal(data.get("total_amount"))
        intent.per_cycle_amount = _to_decimal(data.get("per_cycle_amount"))
        intent.venue = data.get("venue")
        intent.slippage_bps = data.get("slippage_bps")
        intent.stop_conditions = list(data.get("stop_conditions") or [])
        intent.notes = data.get("notes")
        intent.timezone = data.get("timezone")
        intent.confirmed = bool(data.get("confirmed"))
        intent.updated_at = float(data.get("updated_at", time.time()))
        return intent


def datetime_from_timestamp(value: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(value))


# ---------- Session context ----------
_CURRENT_SESSION: ContextVar[tuple[str, str]] = ContextVar("_current_dca_session", default=("", ""))


def set_current_dca_session(user_id: Optional[str], conversation_id: Optional[str]) -> None:
    resolved_user = (user_id or "").strip()
    resolved_conversation = (conversation_id or "").strip()
    if not resolved_user:
        raise ValueError("dca_agent requires 'user_id' to identify the session.")
    if not resolved_conversation:
        raise ValueError("dca_agent requires 'conversation_id' to identify the session.")
    _CURRENT_SESSION.set((resolved_user, resolved_conversation))


@contextmanager
def dca_session(user_id: Optional[str], conversation_id: Optional[str]):
    set_current_dca_session(user_id, conversation_id)
    try:
        yield
    finally:
        clear_current_dca_session()


def clear_current_dca_session() -> None:
    _CURRENT_SESSION.set(("", ""))


def _resolve_session(user_id: Optional[str], conversation_id: Optional[str]) -> tuple[str, str]:
    active_user, active_conversation = _CURRENT_SESSION.get()
    resolved_user = (user_id or active_user or "").strip()
    resolved_conversation = (conversation_id or active_conversation or "").strip()
    if not resolved_user:
        raise ValueError("user_id is required for DCA operations.")
    if not resolved_conversation:
        raise ValueError("conversation_id is required for DCA operations.")
    return resolved_user, resolved_conversation


def _load_intent(user_id: str, conversation_id: str) -> DcaIntent:
    stored = _STORE.load_intent(user_id, conversation_id)
    if stored:
        intent = DcaIntent.from_dict(stored)
        intent.user_id = user_id
        intent.conversation_id = conversation_id
        return intent
    return DcaIntent(user_id=user_id, conversation_id=conversation_id)


# ---------- Metadata helpers ----------
def _store_dca_metadata(
    intent: DcaIntent,
    ask: Optional[str],
    done: bool,
    error: Optional[str],
    choices: Optional[List[str]] = None,
) -> Dict[str, Any]:
    intent.touch()
    missing = intent.missing_fields()
    next_field = intent.next_field()
    meta: Dict[str, Any] = {
        "event": "dca_intent_ready" if done else "dca_intent_collecting",
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
    payload = intent.to_dict()
    meta.update(payload)

    summary = intent.to_summary(error=error) if done else None
    history = _STORE.persist_intent(
        intent.user_id,
        intent.conversation_id,
        payload,
        meta,
        done=done,
        summary=summary,
    )
    if history:
        meta["history"] = history
    metadata.set_dca_agent(meta, intent.user_id, intent.conversation_id)
    return meta


def _build_next_action(meta: Dict[str, Any]) -> Dict[str, Any]:
    if meta.get("status") == "ready":
        return {"type": "complete", "prompt": None, "field": None, "choices": []}
    return {
        "type": "collect_field",
        "prompt": meta.get("pending_question"),
        "field": meta.get("next_field"),
        "choices": meta.get("choices", []),
    }


def _response(
    intent: DcaIntent,
    ask: Optional[str],
    choices: Optional[List[str]] = None,
    done: bool = False,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    meta = _store_dca_metadata(intent, ask, done, error, choices)
    response: Dict[str, Any] = {
        "event": meta.get("event"),
        "intent": intent.to_dict(),
        "ask": ask,
        "choices": choices or [],
        "error": error,
        "next_action": _build_next_action(meta),
        "history": meta.get("history", []),
        "stage": meta.get("stage"),
        "status": meta.get("status"),
    }
    if done:
        response["metadata"] = intent.to_workflow_payload()
    return response


# ---------- Tool Schemas ----------
class FetchStrategyInput(BaseModel):
    user_id: Optional[str] = Field(default=None, description="Stable user identifier.")
    conversation_id: Optional[str] = Field(default=None, description="Conversation identifier.")
    from_token: Optional[str] = Field(default=None, description="Funding token for the DCA.")
    to_token: Optional[str] = Field(default=None, description="Target asset for accumulation.")
    cadence: Optional[str] = Field(default=None, description="Desired cadence cue (daily/weekly/monthly).")
    risk_tier: Optional[str] = Field(default=None, description="Risk tier preference.")
    text: Optional[str] = Field(default=None, description="Additional free-form context to seed retrieval.")
    top_k: int = Field(default=3, ge=1, le=5, description="Maximum number of strategy suggestions to return.")

    @field_validator("cadence", mode="before")
    @classmethod
    def _normalize_cadence(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.lower().strip()
        return value


class UpdateDcaIntentInput(BaseModel):
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    stage: Optional[str] = Field(default=None, description="Explicit stage override (consulting/recommendation/confirmation).")
    strategy_id: Optional[str] = None
    strategy_version: Optional[str] = None
    strategy_name: Optional[str] = None
    strategy_summary: Optional[str] = None
    rag_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    strategy_defaults: Optional[Dict[str, Any]] = None
    guardrails: Optional[List[str]] = None
    compliance_notes: Optional[List[str]] = None
    from_token: Optional[str] = None
    to_token: Optional[str] = None
    cadence: Optional[str] = None
    start_on: Optional[str] = None
    iterations: Optional[int] = Field(default=None, ge=0)
    end_on: Optional[str] = None
    total_amount: Optional[Decimal] = None
    per_cycle_amount: Optional[Decimal] = None
    venue: Optional[str] = None
    slippage_bps: Optional[int] = Field(default=None, ge=0)
    stop_conditions: Optional[List[str]] = None
    notes: Optional[str] = None
    timezone: Optional[str] = None
    confirm: Optional[bool] = None
    reset: bool = Field(default=False, description="When true, clears the current intent.")

    @field_validator("cadence", mode="before")
    @classmethod
    def _norm_cadence(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.lower().strip()
        return value


# ---------- Strategy retrieval tool ----------
@tool("fetch_dca_strategy", args_schema=FetchStrategyInput)
def fetch_dca_strategy_tool(**kwargs) -> Dict[str, Any]:
    """Retrieve strategy recommendations from the registry-backed RAG index."""

    top_k = kwargs.pop("top_k", 3)
    resolved_user, resolved_conversation = _resolve_session(kwargs.get("user_id"), kwargs.get("conversation_id"))
    retriever = get_strategy_retriever()
    matches = retriever.search(
        from_token=kwargs.get("from_token"),
        to_token=kwargs.get("to_token"),
        cadence=kwargs.get("cadence"),
        risk_tier=kwargs.get("risk_tier"),
        text=kwargs.get("text"),
        top_k=top_k,
    )

    suggestions = [match.to_payload() for match in matches]
    intent = _load_intent(resolved_user, resolved_conversation)
    if suggestions:
        best = suggestions[0]
        defaults = dict(best.get("defaults") or {})
        cadence_options = best.get("cadence_options")
        amount_bounds = best.get("amount_bounds")
        slippage_policy = best.get("slippage_bps")

        merged = dict(defaults)
        if cadence_options:
            merged["cadence_options"] = cadence_options
        if amount_bounds:
            merged["amount_bounds"] = amount_bounds
        if slippage_policy:
            merged["slippage_policy"] = slippage_policy
            if "slippage_bps" not in merged and isinstance(slippage_policy, dict):
                merged["slippage_bps"] = slippage_policy.get("recommended")
        intent.strategy_defaults = merged
        intent.guardrails = best.get("guardrails", intent.guardrails)
        intent.compliance_notes = best.get("compliance_notes", intent.compliance_notes)
    meta = _store_dca_metadata(intent, ask=None, done=False, error=None, choices=None)
    return {
        "event": "dca_strategy_suggestions",
        "suggestions": suggestions,
        "query": {
            "from_token": kwargs.get("from_token"),
            "to_token": kwargs.get("to_token"),
            "cadence": kwargs.get("cadence"),
            "risk_tier": kwargs.get("risk_tier"),
            "text": kwargs.get("text"),
        },
        "metadata": meta,
    }


# ---------- Intent update tool ----------
@tool("update_dca_intent", args_schema=UpdateDcaIntentInput)
def update_dca_intent_tool(
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    stage: Optional[str] = None,
    strategy_id: Optional[str] = None,
    strategy_version: Optional[str] = None,
    strategy_name: Optional[str] = None,
    strategy_summary: Optional[str] = None,
    rag_confidence: Optional[float] = None,
    strategy_defaults: Optional[Dict[str, Any]] = None,
    guardrails: Optional[List[str]] = None,
    compliance_notes: Optional[List[str]] = None,
    from_token: Optional[str] = None,
    to_token: Optional[str] = None,
    cadence: Optional[str] = None,
    start_on: Optional[str] = None,
    iterations: Optional[int] = None,
    end_on: Optional[str] = None,
    total_amount: Optional[Decimal] = None,
    per_cycle_amount: Optional[Decimal] = None,
    venue: Optional[str] = None,
    slippage_bps: Optional[int] = None,
    stop_conditions: Optional[List[str]] = None,
    notes: Optional[str] = None,
    timezone: Optional[str] = None,
    confirm: Optional[bool] = None,
    reset: bool = False,
):
    """Update the DCA intent. Supply only freshly provided fields each call."""

    resolved_user, resolved_conversation = _resolve_session(user_id, conversation_id)
    if reset:
        _STORE.clear_intent(resolved_user, resolved_conversation)
        metadata.clear_dca_agent(resolved_user, resolved_conversation)
        intent = DcaIntent(user_id=resolved_user, conversation_id=resolved_conversation)
        return _response(intent, ask="Let's revisit your DCA preferences.", choices=[])

    intent = _load_intent(resolved_user, resolved_conversation)
    intent.user_id = resolved_user
    intent.conversation_id = resolved_conversation

    try:
        if stage:
            intent.advance_stage(stage)
        if strategy_id is not None:
            intent.strategy_id = strategy_id
        if strategy_version is not None:
            intent.strategy_version = strategy_version
        if strategy_name is not None:
            intent.strategy_name = strategy_name
        if strategy_summary is not None:
            intent.strategy_summary = strategy_summary
        if rag_confidence is not None:
            intent.rag_confidence = rag_confidence
        if strategy_defaults is not None:
            intent.strategy_defaults = strategy_defaults
        if guardrails is not None:
            intent.guardrails = list(guardrails)
        if compliance_notes is not None:
            intent.compliance_notes = list(compliance_notes)
        if from_token is not None:
            intent.from_token = from_token
        if to_token is not None:
            intent.to_token = to_token
        if cadence is not None:
            intent.cadence = cadence
        if start_on is not None:
            intent.start_on = start_on
        if iterations is not None:
            intent.iterations = iterations
        if end_on is not None:
            intent.end_on = end_on
        if total_amount is not None:
            intent.total_amount = total_amount
        if per_cycle_amount is not None:
            intent.per_cycle_amount = per_cycle_amount
        if venue is not None:
            intent.venue = venue
        if slippage_bps is not None:
            intent.slippage_bps = slippage_bps
        if stop_conditions is not None:
            intent.stop_conditions = list(stop_conditions)
        if notes is not None:
            intent.notes = notes
        if timezone is not None:
            intent.timezone = timezone

        if confirm is not None:
            intent.confirmed = bool(confirm)
            if intent.confirmed:
                intent.advance_stage("ready")
    except ValueError as exc:
        return _response(intent, ask=intent.next_field() or "Please review the input.", error=str(exc))

    # Stage auto-advancement
    if intent.stage == "consulting" and not intent.missing_fields():
        intent.advance_stage("recommendation")
    if intent.stage == "recommendation" and not intent.missing_fields():
        intent.advance_stage("confirmation")

    missing = intent.missing_fields()
    if (intent.stage == "confirmation" or intent.stage == "ready") and not missing and intent.confirmed:
        return _response(intent, ask=None, done=True)

    ask = _build_prompt_for_field(intent.next_field(), intent)
    choices = _build_choices_for_field(intent.next_field(), intent)
    return _response(intent, ask=ask, choices=choices)


def _build_prompt_for_field(field: Optional[str], intent: DcaIntent) -> Optional[str]:
    prompts = {
        "strategy_id": "Which strategy from the playbook should we base this DCA on?",
        "from_token": "Which token will fund the DCA swaps?",
        "to_token": "Which token should we accumulate?",
        "cadence": "What cadence works best (daily, weekly, monthly)?",
        "start_on": "When should we start the schedule?",
        "iterations_or_end_on": "Provide number of cycles or a target end date.",
        "total_or_per_cycle_amount": "Do you have a total budget or per-cycle amount?",
        "venue": "Where should we route the swaps?",
        "slippage_bps": "Set the maximum slippage tolerance in basis points.",
        "confirmation": "Ready to confirm this workflow?",
    }
    return prompts.get(field)


def _build_choices_for_field(field: Optional[str], intent: DcaIntent) -> List[str]:
    if field == "cadence":
        cadences = intent.strategy_defaults.get("cadence_options") if intent.strategy_defaults else None
        if isinstance(cadences, list):
            return cadences
        cadence_default = intent.strategy_defaults.get("cadence") if intent.strategy_defaults else None
        if cadence_default and isinstance(cadence_default, str):
            return [cadence_default]
    if field == "slippage_bps":
        rec = intent.strategy_defaults.get("slippage_bps") if intent.strategy_defaults else None
        policy = intent.strategy_defaults.get("slippage_policy") if intent.strategy_defaults else None
        if isinstance(rec, dict):
            recommended = rec.get("recommended") or rec.get("default") or rec.get("max")
            if recommended is not None:
                return [str(recommended)]
        if isinstance(rec, (int, float, str)):
            return [str(rec)]
        if isinstance(policy, dict):
            recommended = policy.get("recommended") or policy.get("default") or policy.get("max")
            if recommended is not None:
                return [str(recommended)]
    if field == "iterations_or_end_on":
        defaults = []
        iteration_default = intent.strategy_defaults.get("iterations") if intent.strategy_defaults else None
        end_default = intent.strategy_defaults.get("end_on") if intent.strategy_defaults else None
        if iteration_default is not None:
            defaults.append(f"iterations:{iteration_default}")
        if end_default:
            defaults.append(f"end_on:{end_default}")
        return defaults
    if field == "total_or_per_cycle_amount":
        defaults = []
        if intent.strategy_defaults.get("total_amount"):
            defaults.append(f"total:{intent.strategy_defaults['total_amount']}")
        if intent.strategy_defaults.get("per_cycle_amount"):
            defaults.append(f"per_cycle:{intent.strategy_defaults['per_cycle_amount']}")
        return defaults
    return []


def get_tools():
    return [fetch_dca_strategy_tool, update_dca_intent_tool]
