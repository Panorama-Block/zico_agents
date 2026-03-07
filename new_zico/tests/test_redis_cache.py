import os
import sys
import time
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.infrastructure.redis_cache import RedisJSONCache


class _FakeRedis:
    def __init__(self):
        self._store = {}
        self._exp = {}

    def _alive(self, key: str) -> bool:
        exp = self._exp.get(key)
        if exp is None:
            return key in self._store
        if time.time() > exp:
            self._store.pop(key, None)
            self._exp.pop(key, None)
            return False
        return True

    def ping(self):
        return True

    def get(self, key: str):
        if not self._alive(key):
            return None
        return self._store.get(key)

    def set(self, key: str, value: str, ex: int | None = None):
        self._store[key] = value
        if ex is not None:
            self._exp[key] = time.time() + ex
        return True

    def incr(self, key: str):
        if not self._alive(key):
            self._store[key] = "0"
        value = int(self._store.get(key, "0")) + 1
        self._store[key] = str(value)
        return value

    def expire(self, key: str, ttl: int):
        if key in self._store:
            self._exp[key] = time.time() + ttl
        return True

    def exists(self, key: str):
        return 1 if self._alive(key) else 0


class RedisCacheTest(unittest.TestCase):
    def setUp(self):
        RedisJSONCache._instance = None

    def test_get_set_json_roundtrip(self):
        fake = _FakeRedis()
        with patch.object(RedisJSONCache, "_get_client", return_value=fake):
            cache = RedisJSONCache.instance()
            cache.set_json("k1", {"a": 1}, ttl=2)
            self.assertEqual(cache.get_json("k1"), {"a": 1})

    def test_set_error_payload(self):
        fake = _FakeRedis()
        with patch.object(RedisJSONCache, "_get_client", return_value=fake):
            cache = RedisJSONCache.instance()
            cache.set_error("err", {"kind": "timeout"}, ttl=2)
            payload = cache.get_json("err")
            self.assertTrue(payload.get("__error__"))
            self.assertEqual(payload.get("payload", {}).get("kind"), "timeout")

    def test_redis_unavailable_degrades_gracefully(self):
        with patch.object(RedisJSONCache, "_get_client", return_value=None):
            cache = RedisJSONCache.instance()
            self.assertIsNone(cache.get_json("missing"))
            cache.set_json("k", {"x": 1}, ttl=1)  # no raise
            cache.set_error("e", {"x": "err"}, ttl=1)  # no raise
            self.assertFalse(cache.exists("k"))


if __name__ == "__main__":
    unittest.main()
