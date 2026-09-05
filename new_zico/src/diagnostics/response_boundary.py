from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import time
from typing import Any


_MAX_TRACES = 100

_lock = Lock()
_traces: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()


def _key(user_id: str | None, conversation_id: str | None) -> tuple[str, str] | None:
    if not user_id or not conversation_id:
        return None
    return user_id.strip().lower(), conversation_id.strip()


def start_trace(user_id: str | None, conversation_id: str | None) -> None:
    key = _key(user_id, conversation_id)
    if key is None:
        return

    trace = {
        "conversation_id": key[1],
        "updated_at_unix": time(),
        "agent_messages": None,
        "extracted": None,
        "formatter": None,
        "stream": None,
    }

    with _lock:
        _traces[key] = trace
        _traces.move_to_end(key)

        while len(_traces) > _MAX_TRACES:
            _traces.popitem(last=False)


def update_trace(
    user_id: str | None,
    conversation_id: str | None,
    *,
    section: str,
    value: dict[str, Any],
) -> None:
    key = _key(user_id, conversation_id)
    if key is None:
        return

    with _lock:
        trace = _traces.get(key)
        if trace is None:
            trace = {
                "conversation_id": key[1],
                "updated_at_unix": time(),
                "agent_messages": None,
                "extracted": None,
                "formatter": None,
                "stream": None,
            }
            _traces[key] = trace

        trace[section] = deepcopy(value)
        trace["updated_at_unix"] = time()
        _traces.move_to_end(key)

        while len(_traces) > _MAX_TRACES:
            _traces.popitem(last=False)


def get_latest_trace_for_user(user_id: str | None) -> dict[str, Any] | None:
    if not user_id:
        return None

    normalized = user_id.strip().lower()

    with _lock:
        for (trace_user_id, _conversation_id), trace in reversed(_traces.items()):
            if trace_user_id == normalized:
                return deepcopy(trace)

    return None


def clear_traces_for_tests() -> None:
    with _lock:
        _traces.clear()
