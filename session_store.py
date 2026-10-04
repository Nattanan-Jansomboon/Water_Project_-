"""
In-memory conversation history store, keyed by session_id.

Demo/prototype only -- not persisted, not shared across processes. Swap for
Redis or a DB before this goes anywhere near production traffic.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List

_lock = threading.Lock()
_sessions: Dict[str, List[Dict[str, Any]]] = {}


def get_history(session_id: str) -> List[Dict[str, Any]]:
    with _lock:
        return list(_sessions.get(session_id, []))


def set_history(session_id: str, messages: List[Dict[str, Any]]) -> None:
    with _lock:
        _sessions[session_id] = messages


def clear_history(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)
