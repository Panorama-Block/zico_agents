"""Redis-backed JSON cache with graceful degradation."""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Optional

try:
    import redis
except Exception:  # pragma: no cover - dependency may be absent in local test envs.
    redis = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _to_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _build_redis_url() -> str:
    explicit = (os.getenv("REDIS_URL") or "").strip()
    if explicit:
        return explicit
    host = (os.getenv("REDIS_HOST") or "localhost").strip()
    port = int((os.getenv("REDIS_PORT") or "6379").strip())
    password = os.getenv("REDIS_PASS")
    tls = _to_bool(os.getenv("REDIS_TLS"))
    scheme = "rediss" if tls else "redis"
    if password:
        return f"{scheme}://:{password}@{host}:{port}/0"
    return f"{scheme}://{host}:{port}/0"


class RedisJSONCache:
    """Thread-safe Redis cache helper used across agent live-data flows."""

    _instance: Optional["RedisJSONCache"] = None
    _instance_lock = threading.Lock()

    def __init__(self, namespace: str = "zico:strategy:live_data:") -> None:
        self.namespace = namespace
        self._client: Optional[Any] = None
        self._client_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "RedisJSONCache":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _key(self, key: str) -> str:
        return f"{self.namespace}{key}"

    def _get_client(self) -> Optional[Any]:
        if redis is None:
            return None
        if self._client is not None:
            return self._client
        with self._client_lock:
            if self._client is not None:
                return self._client
            try:
                client = redis.Redis.from_url(
                    _build_redis_url(),
                    decode_responses=True,
                    socket_connect_timeout=1.5,
                    socket_timeout=1.5,
                    health_check_interval=30,
                    retry_on_timeout=True,
                )
                client.ping()
                self._client = client
                return client
            except Exception as exc:
                logger.warning("Redis unavailable; cache will degrade to source fetches: %s", exc)
                self._client = None
                return None

    def get_json(self, key: str) -> Any:
        client = self._get_client()
        if client is None:
            return None
        try:
            raw = client.get(self._key(key))
            if not raw:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.debug("Redis get_json failed for key=%s: %s", key, exc)
            return None

    def set_json(self, key: str, value: Any, ttl: int) -> None:
        client = self._get_client()
        if client is None:
            return
        try:
            payload = json.dumps(value, separators=(",", ":"), ensure_ascii=True)
            client.set(self._key(key), payload, ex=max(int(ttl), 1))
        except Exception as exc:
            logger.debug("Redis set_json failed for key=%s: %s", key, exc)

    def set_error(self, key: str, error_payload: Any, ttl: int) -> None:
        wrapped = {"__error__": True, "payload": error_payload}
        self.set_json(key, wrapped, ttl)

    def incr(self, key: str, ttl: int) -> int:
        client = self._get_client()
        if client is None:
            return 0
        try:
            nkey = self._key(key)
            value = int(client.incr(nkey))
            if value == 1:
                client.expire(nkey, max(int(ttl), 1))
            return value
        except Exception as exc:
            logger.debug("Redis incr failed for key=%s: %s", key, exc)
            return 0

    def exists(self, key: str) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            return bool(client.exists(self._key(key)))
        except Exception as exc:
            logger.debug("Redis exists failed for key=%s: %s", key, exc)
            return False
