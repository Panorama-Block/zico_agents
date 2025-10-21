"""Gateway-backed storage for swap intents with local fallback."""
from __future__ import annotations

import copy
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

from src.integrations.panorama_gateway import (
    PanoramaGatewayClient,
    PanoramaGatewayError,
    PanoramaGatewaySettings,
    get_panorama_settings,
)

SWAP_SESSION_ENTITY = "swap-sessions"
SWAP_HISTORY_ENTITY = "swap-histories"


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


def _identifier(user_id: str, conversation_id: str) -> str:
    return f"{user_id}:{conversation_id}"


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class SwapStateRepository:
    """Stores swap agent state via Panorama's gateway or an in-memory fallback."""

    _instance: "SwapStateRepository" | None = None
    _instance_lock: Lock = Lock()

    def __init__(
        self,
        *,
        client: PanoramaGatewayClient | None = None,
        settings: PanoramaGatewaySettings | None = None,
        history_limit: int = 10,
    ) -> None:
        self._history_limit = history_limit
        try:
            self._settings = settings or get_panorama_settings()
            self._client = client or PanoramaGatewayClient(self._settings)
            self._use_gateway = True
        except ValueError:
            # PANORAMA_GATEWAY_URL or JWT secrets not configured – fall back to local store.
            self._settings = None
            self._client = None
            self._use_gateway = False
            self._state = {"intents": {}, "metadata": {}, "history": {}}

    # ---- Singleton helpers -----------------------------------------------
    @classmethod
    def instance(cls) -> "SwapStateRepository":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._instance_lock:
            cls._instance = None

    # ---- Core API ---------------------------------------------------------
    def load_intent(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        if not self._use_gateway:
            record = self._state["intents"].get(_identifier(user_id, conversation_id))
            if not record:
                return None
            return copy.deepcopy(record.get("intent"))

        session = self._get_session(user_id, conversation_id)
        if not session:
            return None
        return session.get("intent") or None

    def persist_intent(
        self,
        user_id: str,
        conversation_id: str,
        intent: Dict[str, Any],
        metadata: Dict[str, Any],
        done: bool,
        summary: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not self._use_gateway:
            key = _identifier(user_id, conversation_id)
            now = time.time()
            if done:
                self._state["intents"].pop(key, None)
            else:
                self._state["intents"][key] = {"intent": copy.deepcopy(intent), "updated_at": now}
            if metadata:
                meta_copy = copy.deepcopy(metadata)
                meta_copy["updated_at"] = now
                self._state["metadata"][key] = meta_copy
            if done and summary:
                history = self._state["history"].setdefault(key, [])
                summary_copy = copy.deepcopy(summary)
                summary_copy.setdefault("timestamp", now)
                history.append(summary_copy)
                self._state["history"][key] = history[-self._history_limit :]
            return self.get_history(user_id, conversation_id)

        if done:
            if summary:
                self._create_history_entry(user_id, conversation_id, summary)
            self._delete_session(user_id, conversation_id)
        else:
            payload = self._session_payload(intent, metadata)
            self._upsert_session(user_id, conversation_id, payload)
        return self.get_history(user_id, conversation_id)

    def set_metadata(
        self,
        user_id: str,
        conversation_id: str,
        metadata: Dict[str, Any],
    ) -> None:
        if not self._use_gateway:
            key = _identifier(user_id, conversation_id)
            if metadata:
                meta_copy = copy.deepcopy(metadata)
                meta_copy["updated_at"] = time.time()
                self._state["metadata"][key] = meta_copy
            else:
                self._state["metadata"].pop(key, None)
            return

        if not metadata:
            self._delete_session(user_id, conversation_id)
            return

        session = self._get_session(user_id, conversation_id)
        intent = session.get("intent") if session else {}
        payload = self._session_payload(intent or {}, metadata)
        self._upsert_session(user_id, conversation_id, payload)

    def clear_metadata(self, user_id: str, conversation_id: str) -> None:
        self.set_metadata(user_id, conversation_id, {})

    def clear_intent(self, user_id: str, conversation_id: str) -> None:
        if not self._use_gateway:
            self._state["intents"].pop(_identifier(user_id, conversation_id), None)
            self._state["metadata"].pop(_identifier(user_id, conversation_id), None)
            return
        self._delete_session(user_id, conversation_id)

    def get_metadata(self, user_id: str, conversation_id: str) -> Dict[str, Any]:
        if not self._use_gateway:
            record = self._state["metadata"].get(_identifier(user_id, conversation_id))
            if not record:
                return {}
            entry = copy.deepcopy(record)
            ts = entry.pop("updated_at", None)
            if ts is not None:
                entry["updated_at"] = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
            return entry

        session = self._get_session(user_id, conversation_id)
        if not session:
            return {}

        intent = session.get("intent") or {}
        metadata: Dict[str, Any] = {
            "event": session.get("event"),
            "status": session.get("status"),
            "missing_fields": session.get("missingFields") or [],
            "next_field": session.get("nextField"),
            "pending_question": session.get("pendingQuestion"),
            "choices": session.get("choices") or [],
            "error": session.get("errorMessage"),
            "user_id": user_id,
            "conversation_id": conversation_id,
        }
        metadata["from_network"] = intent.get("from_network")
        metadata["from_token"] = intent.get("from_token")
        metadata["to_network"] = intent.get("to_network")
        metadata["to_token"] = intent.get("to_token")
        metadata["amount"] = intent.get("amount")

        history = self.get_history(user_id, conversation_id)
        if history:
            metadata["history"] = history

        updated_at = session.get("updatedAt")
        if updated_at:
            metadata["updated_at"] = updated_at

        return metadata

    def get_history(
        self,
        user_id: str,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if not self._use_gateway:
            key = _identifier(user_id, conversation_id)
            history = self._state["history"].get(key, [])
            effective = limit or self._history_limit
            result: List[Dict[str, Any]] = []
            for item in sorted(history, key=lambda entry: entry.get("timestamp", 0), reverse=True)[:effective]:
                entry = copy.deepcopy(item)
                ts = entry.get("timestamp")
                if ts is not None:
                    entry["timestamp"] = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
                result.append(entry)
            return result

        effective_limit = limit or self._history_limit
        result = self._client.list(
            SWAP_HISTORY_ENTITY,
            {
                "where": {"userId": user_id, "conversationId": conversation_id},
                "orderBy": {"recordedAt": "desc"},
                "take": effective_limit,
            },
        )
        data = result.get("data", []) if isinstance(result, dict) else []
        history: List[Dict[str, Any]] = []
        for entry in data:
            history.append(
                {
                    "status": entry.get("status"),
                    "from_network": entry.get("fromNetwork"),
                    "from_token": entry.get("fromToken"),
                    "to_network": entry.get("toNetwork"),
                    "to_token": entry.get("toToken"),
                    "amount": entry.get("amount"),
                    "error": entry.get("errorMessage"),
                    "timestamp": entry.get("recordedAt"),
                }
            )
        return history

    # ---- Gateway helpers --------------------------------------------------
    def _get_session(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        identifier = _identifier(user_id, conversation_id)
        try:
            return self._client.get(SWAP_SESSION_ENTITY, identifier)
        except PanoramaGatewayError as exc:
            if exc.status_code == 404:
                return None
            raise

    def _delete_session(self, user_id: str, conversation_id: str) -> None:
        identifier = _identifier(user_id, conversation_id)
        try:
            self._client.delete(SWAP_SESSION_ENTITY, identifier)
        except PanoramaGatewayError as exc:
            if exc.status_code != 404:
                raise

    def _upsert_session(
        self,
        user_id: str,
        conversation_id: str,
        data: Dict[str, Any],
    ) -> None:
        identifier = _identifier(user_id, conversation_id)
        payload = {**data, "updatedAt": _utc_now_iso()}
        try:
            self._client.update(SWAP_SESSION_ENTITY, identifier, payload)
        except PanoramaGatewayError as exc:
            if exc.status_code != 404:
                raise
            create_payload = {
                "userId": user_id,
                "conversationId": conversation_id,
                "tenantId": self._settings.tenant_id,
                **payload,
            }
            self._client.create(SWAP_SESSION_ENTITY, create_payload)

    def _create_history_entry(
        self,
        user_id: str,
        conversation_id: str,
        summary: Dict[str, Any],
    ) -> None:
        history_payload = {
            "userId": user_id,
            "conversationId": conversation_id,
            "status": summary.get("status"),
            "fromNetwork": summary.get("from_network"),
            "fromToken": summary.get("from_token"),
            "toNetwork": summary.get("to_network"),
            "toToken": summary.get("to_token"),
            "amount": _as_float(summary.get("amount")),
            "errorMessage": summary.get("error"),
            "recordedAt": _utc_now_iso(),
            "tenantId": self._settings.tenant_id,
        }
        self._client.create(SWAP_HISTORY_ENTITY, history_payload)

    @staticmethod
    def _session_payload(intent: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        missing = metadata.get("missing_fields") or []
        if not isinstance(missing, list):
            missing = list(missing)
        return {
            "status": metadata.get("status"),
            "event": metadata.get("event"),
            "intent": intent,
            "missingFields": missing,
            "nextField": metadata.get("next_field"),
            "pendingQuestion": metadata.get("pending_question"),
            "choices": metadata.get("choices"),
            "errorMessage": metadata.get("error"),
            "historyCursor": metadata.get("history_cursor") or 0,
        }
