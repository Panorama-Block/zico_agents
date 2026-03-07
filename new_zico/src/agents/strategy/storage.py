"""State management for strategy intents with optional Panorama gateway persistence."""

from __future__ import annotations

import copy
import logging
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

SHARED_STATE_ENTITY = "agent-shared-states"
STRATEGY_HISTORY_ENTITY = "strategy-histories"
STRATEGY_AGENT_NAME = "strategy_agent"


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


def _identifier(user_id: str, conversation_id: str) -> str:
    return f"{user_id}:{conversation_id}"


class StrategyStateRepository:
    """Stores strategy agent state via Panorama gateway with local fallback."""

    _instance: "StrategyStateRepository" | None = None
    _instance_lock: Lock = Lock()

    def __init__(
        self,
        *,
        client: PanoramaGatewayClient | None = None,
        settings: PanoramaGatewaySettings | None = None,
        history_limit: int = 10,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._history_limit = history_limit
        self._remote_history_supported = True
        self._history_warning_emitted = False
        try:
            self._settings = settings or get_panorama_settings()
            self._client = client or PanoramaGatewayClient(self._settings)
            self._use_gateway = True
        except ValueError:
            self._settings = None
            self._client = None
            self._use_gateway = False
        self._init_local_store()

    def _init_local_store(self) -> None:
        if not hasattr(self, "_state"):
            self._state = {"intents": {}, "metadata": {}, "history": {}}

    def _tenant_id(self) -> str:
        return self._settings.tenant_id if self._settings else "tenant-agent"

    def _session_identifier(self, user_id: str, conversation_id: str) -> str:
        return f"{STRATEGY_AGENT_NAME}:{user_id}:{conversation_id}"

    @staticmethod
    def _is_unknown_entity_error(exc: PanoramaGatewayError, entity: str) -> bool:
        if exc.status_code != 400:
            return False
        payload = getattr(exc, "payload", None)
        if isinstance(payload, dict):
            message = str(payload.get("message") or "").lower()
            return f"unknown entity: {entity}".lower() in message or f"unknown entity {entity}".lower() in message
        return False

    def _disable_remote_history(self) -> None:
        self._remote_history_supported = False
        if not self._history_warning_emitted:
            self._history_warning_emitted = True
            self._logger.warning(
                "Panorama gateway does not support '%s'; strategy history will use local fallback.",
                STRATEGY_HISTORY_ENTITY,
            )

    def _fallback_to_local_store(self) -> None:
        if self._use_gateway:
            self._logger.warning("Panorama gateway unavailable for strategy state; switching to in-memory fallback.")
        self._use_gateway = False
        self._init_local_store()

    def _handle_gateway_failure(self, exc: PanoramaGatewayError) -> None:
        self._logger.warning(
            "Panorama gateway error (%s) for strategy repository: %s",
            getattr(exc, "status_code", "unknown"),
            getattr(exc, "payload", exc),
        )
        self._fallback_to_local_store()

    def _get_local_history(self, user_id: str, conversation_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        self._init_local_store()
        history = self._state["history"].get(_identifier(user_id, conversation_id), [])
        if not history:
            return []
        records = copy.deepcopy(history)
        if limit:
            records = records[-limit:]
        for record in records:
            ts = record.get("timestamp")
            if ts is not None:
                record["timestamp"] = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
        return records

    def _append_local_history(self, user_id: str, conversation_id: str, summary: Dict[str, Any]) -> None:
        key = _identifier(user_id, conversation_id)
        history = self._state["history"].setdefault(key, [])
        item = copy.deepcopy(summary)
        item.setdefault("timestamp", time.time())
        history.append(item)
        self._state["history"][key] = history[-self._history_limit :]

    @classmethod
    def instance(cls) -> "StrategyStateRepository":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._instance_lock:
            cls._instance = None

    def load_intent(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        if not self._use_gateway:
            self._init_local_store()
            record = self._state["intents"].get(_identifier(user_id, conversation_id))
            if not record:
                return None
            return copy.deepcopy(record.get("intent"))

        session = self._get_session(user_id, conversation_id)
        if not self._use_gateway:
            return self.load_intent(user_id, conversation_id)
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
            self._init_local_store()
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

        try:
            if done:
                if summary:
                    self._create_history_entry(user_id, conversation_id, summary)
                    if not self._remote_history_supported:
                        self._append_local_history(user_id, conversation_id, summary)
                self._delete_session(user_id, conversation_id)
            else:
                payload = self._session_payload(intent, metadata)
                self._upsert_session(user_id, conversation_id, payload)
            return self.get_history(user_id, conversation_id)
        except PanoramaGatewayError as exc:
            self._handle_gateway_failure(exc)
            return self.persist_intent(user_id, conversation_id, intent, metadata, done, summary)

    def set_metadata(self, user_id: str, conversation_id: str, metadata: Dict[str, Any]) -> None:
        if not self._use_gateway:
            self._init_local_store()
            key = _identifier(user_id, conversation_id)
            if metadata:
                meta_copy = copy.deepcopy(metadata)
                meta_copy["updated_at"] = time.time()
                self._state["metadata"][key] = meta_copy
            else:
                self._state["metadata"].pop(key, None)
            return

        try:
            if not metadata:
                self._delete_session(user_id, conversation_id)
                return
            session = self._get_session(user_id, conversation_id)
            if not self._use_gateway:
                return self.set_metadata(user_id, conversation_id, metadata)
            intent = session.get("intent") if session else {}
            payload = self._session_payload(intent or {}, metadata)
            self._upsert_session(user_id, conversation_id, payload)
        except PanoramaGatewayError as exc:
            self._handle_gateway_failure(exc)
            self.set_metadata(user_id, conversation_id, metadata)

    def clear_metadata(self, user_id: str, conversation_id: str) -> None:
        self.set_metadata(user_id, conversation_id, {})

    def clear_intent(self, user_id: str, conversation_id: str) -> None:
        if not self._use_gateway:
            self._init_local_store()
            key = _identifier(user_id, conversation_id)
            self._state["intents"].pop(key, None)
            self._state["metadata"].pop(key, None)
            return
        try:
            self._delete_session(user_id, conversation_id)
        except PanoramaGatewayError as exc:
            self._handle_gateway_failure(exc)
            self.clear_intent(user_id, conversation_id)

    def get_metadata(self, user_id: str, conversation_id: str) -> Dict[str, Any]:
        if not self._use_gateway:
            self._init_local_store()
            record = self._state["metadata"].get(_identifier(user_id, conversation_id))
            if not record:
                return {}
            entry = copy.deepcopy(record)
            ts = entry.pop("updated_at", None)
            if ts is not None:
                entry["updated_at"] = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
            return entry

        session = self._get_session(user_id, conversation_id)
        if not self._use_gateway:
            return self.get_metadata(user_id, conversation_id)
        if not session:
            return {}

        intent = session.get("intent") or {}
        metadata: Dict[str, Any] = {
            "event": session.get("event"),
            "status": session.get("status"),
            "stage": session.get("stage"),
            "missing_fields": session.get("missingFields") or [],
            "next_field": session.get("nextField"),
            "pending_question": session.get("pendingQuestion"),
            "choices": session.get("choices") or [],
            "error": session.get("errorMessage"),
            "user_id": user_id,
            "conversation_id": conversation_id,
        }
        metadata.update(intent)

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
            return self._get_local_history(user_id, conversation_id, limit)

        effective_limit = limit or self._history_limit
        if not self._remote_history_supported:
            return self._get_local_history(user_id, conversation_id, limit)
        try:
            result = self._client.list(
                STRATEGY_HISTORY_ENTITY,
                {
                    "where": {"userId": user_id, "conversationId": conversation_id},
                    "orderBy": {"recordedAt": "desc"},
                    "take": effective_limit,
                },
            )
        except PanoramaGatewayError as exc:
            if exc.status_code == 404:
                return []
            if self._is_unknown_entity_error(exc, STRATEGY_HISTORY_ENTITY):
                self._disable_remote_history()
                return self._get_local_history(user_id, conversation_id, limit)
            self._handle_gateway_failure(exc)
            return self.get_history(user_id, conversation_id, limit)
        except ValueError:
            self._logger.warning("Invalid strategy history response from gateway; falling back to local store.")
            self._fallback_to_local_store()
            return self.get_history(user_id, conversation_id, limit)

        data = result.get("data", []) if isinstance(result, dict) else []
        history: List[Dict[str, Any]] = []
        for entry in data:
            payload = entry.get("metadata") or {}
            history.append(
                {
                    "timestamp": entry.get("recordedAt"),
                    "summary": entry.get("summary") or payload.get("summary"),
                    "metadata": payload,
                }
            )
        return history

    def _session_payload(self, intent: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "intent": intent,
            "event": metadata.get("event"),
            "status": metadata.get("status"),
            "stage": metadata.get("stage"),
            "missingFields": metadata.get("missing_fields") or [],
            "nextField": metadata.get("next_field"),
            "pendingQuestion": metadata.get("pending_question"),
            "choices": metadata.get("choices") or [],
            "errorMessage": metadata.get("error"),
            "updatedAt": metadata.get("updated_at") or _utc_now_iso(),
        }

    def _get_session(self, user_id: str, conversation_id: str) -> Dict[str, Any] | None:
        identifier = self._session_identifier(user_id, conversation_id)
        try:
            record = self._client.get(SHARED_STATE_ENTITY, identifier)
            state = record.get("state") if isinstance(record, dict) else None
            return state if isinstance(state, dict) else None
        except PanoramaGatewayError as exc:
            if exc.status_code == 404:
                return None
            self._handle_gateway_failure(exc)
            return None

    def _upsert_session(self, user_id: str, conversation_id: str, payload: Dict[str, Any]) -> None:
        identifier = self._session_identifier(user_id, conversation_id)
        record = {"state": payload, "updatedAt": _utc_now_iso()}
        try:
            self._client.update(SHARED_STATE_ENTITY, identifier, record)
        except PanoramaGatewayError as exc:
            if exc.status_code != 404:
                raise
            create_payload = {
                "agentName": STRATEGY_AGENT_NAME,
                "userId": user_id,
                "conversationId": conversation_id,
                "tenantId": self._tenant_id(),
                **record,
            }
            try:
                self._client.create(SHARED_STATE_ENTITY, create_payload)
            except PanoramaGatewayError as create_exc:
                if create_exc.status_code == 409:
                    return
                raise

    def _delete_session(self, user_id: str, conversation_id: str) -> None:
        identifier = self._session_identifier(user_id, conversation_id)
        try:
            self._client.delete(SHARED_STATE_ENTITY, identifier)
        except PanoramaGatewayError as exc:
            if exc.status_code != 404:
                self._handle_gateway_failure(exc)
                raise

    def _create_history_entry(self, user_id: str, conversation_id: str, summary: Dict[str, Any]) -> None:
        if not self._remote_history_supported:
            return
        payload = {
            "userId": user_id,
            "conversationId": conversation_id,
            "summary": summary.get("summary"),
            "metadata": summary,
            "recordedAt": _utc_now_iso(),
            "tenantId": self._tenant_id(),
        }
        try:
            self._client.create(STRATEGY_HISTORY_ENTITY, payload)
        except PanoramaGatewayError as exc:
            if exc.status_code == 409:
                return
            if self._is_unknown_entity_error(exc, STRATEGY_HISTORY_ENTITY):
                self._disable_remote_history()
                return
            raise
