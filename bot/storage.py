"""Tiny JSON store: remembers which clips we've already notified about."""
import json
import os
import threading

from . import config

_PATH = os.path.join(config.DATA_DIR, "state.json")
_lock = threading.Lock()


def _load() -> dict:
    if os.path.exists(_PATH):
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"seen": [], "decided": {}}


def _save(state: dict) -> None:
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _PATH)


def is_seen(clip_id: str) -> bool:
    with _lock:
        return clip_id in _load()["seen"]


def mark_seen(clip_id: str) -> None:
    with _lock:
        s = _load()
        if clip_id not in s["seen"]:
            s["seen"].append(clip_id)
            _save(s)


def mark_decided(clip_id: str, decision: str) -> None:
    with _lock:
        s = _load()
        s["decided"][clip_id] = decision
        _save(s)
