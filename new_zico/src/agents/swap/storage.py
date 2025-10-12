"""Persistent storage for swap intents and metadata."""
from __future__ import annotations

import copy
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

_STATE_TEMPLATE: Dict[str, Dict[str, Any]] = {
    "intents": {},
    "metadata": {},
    "history": {},
}


class SwapStateRepository:
    """File-backed storage for swap agent state with TTL and history support."""

    _instance: "SwapStateRepository" | None = None
    _instance_lock: Lock = Lock()

    def __init__(
        self,
        path: Optional[Path] = None,
        ttl_seconds: int = 3600,
        history_limit: int = 10,
    ) -> None:
        env_path = os.getenv("SWAP_STATE_PATH")
        default_path = Path(__file__).with_name("swap_state.json")
        self._path = Path(path or env_path or default_path)
        self._ttl_seconds = ttl_seconds
        self._history_limit = history_limit
        self._lock = Lock()
        self._state: Dict[str, Dict[str, Any]] = copy.deepcopy(_STATE_TEMPLATE)
        self._ensure_parent()
        with self._lock:
            self._load_locked()

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

    def _ensure_parent(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def _load_locked(self) -> None:
        if not self._path.exists():
            self._state = copy.deepcopy(_STATE_TEMPLATE)
            return
        try:
            data = json.loads(self._path.read_text())
        except Exception:
            self._state = copy.deepcopy(_STATE_TEMPLATE)
            return
        if not isinstance(data, dict):
            self._state = copy.deepcopy(_STATE_TEMPLATE)
            return
        state = copy.deepcopy(_STATE_TEMPLATE)
        for key in state:
            if isinstance(data.get(key), dict):
                state[key] = data[key]
        self._state = state

    def _persist_locked(self) -> None:
        self._ensure_parent()
        tmp_path = self._path.with_suffix(".tmp")
        payload = json.dumps(self._state, ensure_ascii=False, indent=2)
        try:
            tmp_path.write_text(payload)
            tmp_path.replace(self._path)
        except Exception:
            pass

    @staticmethod
    def _normalize_identifier(value: Optional[str], label: str) -> str:
        candidate = (value or "").strip()
        if not candidate:
            raise ValueError(f"{label} is required for swap state operations.")
        return candidate

    def _key(self, user_id: Optional[str], conversation_id: Optional[str]) -> str:
        user = self._normalize_identifier(user_id, "user_id")
        conversation = self._normalize_identifier(conversation_id, "conversation_id")
        return f"{user}::{conversation}"

    def _purge_locked(self) -> None:
        if self._ttl_seconds <= 0:
            return
        cutoff = time.time() - self._ttl_seconds
        intents = self._state["intents"]
        metadata = self._state["metadata"]
        stale_keys = [
            key for key, record in intents.items() if record.get("updated_at", 0) < cutoff
        ]
        for key in stale_keys:
            intents.pop(key, None)
            metadata.pop(key, None)

    @staticmethod
    def _format_timestamp(value: float) -> str:
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()

    def _history_unlocked(self, key: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        history = self._state["history"].get(key, [])
        sorted_history = sorted(history, key=lambda item: item.get("timestamp", 0), reverse=True)
        effective_limit = limit or self._history_limit
        if effective_limit:
            sorted_history = sorted_history[:effective_limit]
        results: List[Dict[str, Any]] = []
        for item in sorted_history:
            entry = copy.deepcopy(item)
            ts = entry.get("timestamp")
            if ts is not None:
                entry["timestamp"] = self._format_timestamp(float(ts))
            results.append(entry)
        return results

    def load_intent(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        key = self._key(user_id, conversation_id)
        with self._lock:
            self._purge_locked()
            record = self._state["intents"].get(key)
            if not record:
                return None
            return copy.deepcopy(record.get("intent"))

    def persist_intent(
        self,
        user_id: str,
        conversation_id: str,
        intent: Dict[str, Any],
        metadata: Dict[str, Any],
        done: bool,
        summary: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        key = self._key(user_id, conversation_id)
        with self._lock:
            self._purge_locked()
            now = time.time()
            if done:
                self._state["intents"].pop(key, None)
            else:
                self._state["intents"][key] = {
                    "intent": copy.deepcopy(intent),
                    "updated_at": now,
                }
            if metadata:
                meta_copy = copy.deepcopy(metadata)
                meta_copy["updated_at"] = now
                self._state["metadata"][key] = meta_copy
            if done and summary:
                history = self._state["history"].get(key, [])
                summary_copy = copy.deepcopy(summary)
                summary_copy.setdefault("timestamp", now)
                history.append(summary_copy)
                self._state["history"][key] = history[-self._history_limit:]
            try:
                self._persist_locked()
            except Exception:
                pass
            return self._history_unlocked(key)

    def set_metadata(self, user_id: str, conversation_id: str, metadata: Dict[str, Any]) -> None:
        key = self._key(user_id, conversation_id)
        with self._lock:
            self._purge_locked()
            if metadata:
                meta_copy = copy.deepcopy(metadata)
                meta_copy["updated_at"] = time.time()
                self._state["metadata"][key] = meta_copy
            else:
                self._state["metadata"].pop(key, None)
            try:
                self._persist_locked()
            except Exception:
                pass

    def clear_metadata(self, user_id: str, conversation_id: str) -> None:
        self.set_metadata(user_id, conversation_id, {})

    def clear_intent(self, user_id: str, conversation_id: str) -> None:
        key = self._key(user_id, conversation_id)
        with self._lock:
            self._state["intents"].pop(key, None)
            try:
                self._persist_locked()
            except Exception:
                pass

    def get_metadata(self, user_id: str, conversation_id: str) -> Dict[str, Any]:
        key = self._key(user_id, conversation_id)
        with self._lock:
            self._purge_locked()
            meta = self._state["metadata"].get(key)
            if not meta:
                return {}
            entry = copy.deepcopy(meta)
            ts = entry.pop("updated_at", None)
            if ts is not None:
                entry["updated_at"] = self._format_timestamp(float(ts))
            return entry

    def get_history(
        self,
        user_id: str,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        key = self._key(user_id, conversation_id)
        with self._lock:
            return self._history_unlocked(key, limit)

