"""Tiny JSON-file store for to-do "done" state.

To-dos are regenerated on each refresh, so we persist only their checked state,
keyed by a stable id (``<message_id>:<index>``). This keeps ticked-off items
ticked across refreshes and restarts.
"""

from __future__ import annotations

import json
import threading
from typing import Dict

from . import config

_lock = threading.Lock()


def _load() -> Dict[str, bool]:
    path = config.TODO_STATE_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(state: Dict[str, bool]) -> None:
    config.ensure_cache_dir()
    config.TODO_STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def is_done(todo_id: str) -> bool:
    with _lock:
        return bool(_load().get(todo_id, False))


def get_many(todo_ids) -> Dict[str, bool]:
    with _lock:
        state = _load()
        return {tid: bool(state.get(tid, False)) for tid in todo_ids}


def set_done(todo_id: str, done: bool) -> None:
    with _lock:
        state = _load()
        if done:
            state[todo_id] = True
        else:
            state.pop(todo_id, None)
        _save(state)
