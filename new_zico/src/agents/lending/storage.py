"""Gateway-backed storage for lending intents with local fallback."""
from __future__ import annotations

import copy
import time
import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

from src.integrations.panorama_gateway import (
    PanoramaGatewayClient,
    PanoramaGatewayError,
    PanoramaGatewaySettings,
    get_panorama_settings,
)

LENDING_SESSION_ENTITY = "lending-sessions"
LENDING_HISTORY_ENTITY = "lending-histories"


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


class LendingStateRepository:
    """Stores lending agent state via Panorama's gateway or an in-memory fallback."""

    _instance: "LendingStateRepository" | None = None
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
        try:
            self._settings = settings or get_panorama_settings()
            self._client = client or PanoramaGatewayClient(self._settings)
            self._use_gateway = True
        except ValueError:
            # PANORAMA_GATEWAY_URL or JWT secrets not configured – fall back to local store.
            self._settings = None
            self._client = None
            self._use_gateway = False
        self._init_local_store()

    def _init_local_store(self) -> None:
        if not hasattr(self, "_state"):
            self._state = {"intents": {}, "metadata": {}, "history": {}}

    def _tenant_id(self) -> str:
        return self._settings.tenant_id if self._settings else "tenant-agent"

    def _fallback_to_local_store(self) -> None:
        if self._use_gateway:
            self._logger.warning("Panorama gateway unavailable for lending state; switching to in-memory fallback.")
        self._use_gateway = False
        self._init_local_store()

    def _handle_gateway_failure(self, exc: PanoramaGatewayError) -> None:
        self._logger.warning(
            "Panorama gateway error (%s) for lending repository: %s",
            getattr(exc, "status_code", "unknown"),
            getattr(exc, "payload", exc),
        )
        self._fallback_to_local_store()

    # ---- Singleton helpers -----------------------------------------------
    @classmethod
    def instance(cls) -> "LendingStateRepository":
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
                self._delete_session(user_id, conversation_id)
            else:
                payload = self._session_payload(intent, metadata)
                self._upsert_session(user_id, conversation_id, payload)
            return self.get_history(user_id, conversation_id)
        except PanoramaGatewayError as exc:
            self._handle_gateway_failure(exc)
            return self.persist_intent(user_id, conversation_id, intent, metadata, done, summary)

    def set_metadata(
        self,
        user_id: str,
        conversation_id: str,
        metadata: Dict[str, Any],
    ) -> None:
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
            self._state["intents"].pop(_identifier(user_id, conversation_id), None)
            self._state["metadata"].pop(_identifier(user_id, conversation_id), None)
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
            "missing_fields": session.get("missingFields") or [],
            "next_field": session.get("nextField"),
            "pending_question": session.get("pendingQuestion"),
            "choices": session.get("choices") or [],
            "error": session.get("errorMessage"),
            "user_id": user_id,
            "conversation_id": conversation_id,
        }
        metadata["action"] = intent.get("action")
        metadata["network"] = intent.get("network")
        metadata["asset"] = intent.get("asset")
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
        try:
            result = self._client.list(
                LENDING_HISTORY_ENTITY,
                {
                    "where": {"userId": user_id, "conversationId": conversation_id},
                    "orderBy": {"recordedAt": "desc"},
                    "take": effective_limit,
                },
            )
        except PanoramaGatewayError as exc:
            if exc.status_code == 404:
                return []
            self._handle_gateway_failure(exc)
            return self.get_history(user_id, conversation_id, limit)
        except ValueError:
            self._logger.warning("Invalid lending history response from gateway; falling back to local store.")
            self._fallback_to_local_store()
            return self.get_history(user_id, conversation_id, limit)
        data = result.get("data", []) if isinstance(result, dict) else []
        history: List[Dict[str, Any]] = []
        for entry in data:
            history.append(
                {
                    "status": entry.get("status"),
                    "action": entry.get("action"),
                    "network": entry.get("network"),
                    "asset": entry.get("asset"),
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
            return self._client.get(LENDING_SESSION_ENTITY, identifier)
        except PanoramaGatewayError as exc:
            if exc.status_code == 404:
                return None
            self._handle_gateway_failure(exc)
            return None

    def _delete_session(self, user_id: str, conversation_id: str) -> None:
        identifier = _identifier(user_id, conversation_id)
        try:
            self._client.delete(LENDING_SESSION_ENTITY, identifier)
        except PanoramaGatewayError as exc:
            if exc.status_code != 404:
                self._handle_gateway_failure(exc)
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
            self._client.update(LENDING_SESSION_ENTITY, identifier, payload)
        except PanoramaGatewayError as exc:
            if exc.status_code != 404:
                self._handle_gateway_failure(exc)
                raise
            create_payload = {
                "userId": user_id,
                "conversationId": conversation_id,
                "tenantId": self._tenant_id(),
                **payload,
            }
            try:
                self._client.create(LENDING_SESSION_ENTITY, create_payload)
            except PanoramaGatewayError as create_exc:
                if create_exc.status_code == 409:
                    return
                if create_exc.status_code == 404:
                    self._handle_gateway_failure(create_exc)
                    raise
                self._handle_gateway_failure(create_exc)
                raise

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
            "action": summary.get("action"),
            "network": summary.get("network"),
            "asset": summary.get("asset"),
            "amount": _as_float(summary.get("amount")),
            "errorMessage": summary.get("error"),
            "recordedAt": _utc_now_iso(),
            "tenantId": self._tenant_id(),
        }
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(
                "Persisting lending history for user=%s conversation=%s payload=%s",
                user_id,
                conversation_id,
                history_payload,
            )
        try:
            self._client.create(LENDING_HISTORY_ENTITY, history_payload)
        except PanoramaGatewayError as exc:
            if exc.status_code == 404:
                self._handle_gateway_failure(exc)
                raise
            elif exc.status_code != 409:
                self._handle_gateway_failure(exc)
                raise

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
