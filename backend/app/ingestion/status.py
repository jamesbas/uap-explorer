"""Ingestion run status, persisted to disk so it survives restarts."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings

_LOCK = threading.Lock()
_STATE_FILE: Path = settings.processed_root / "ingestion_status.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_state() -> Dict[str, Any]:
    return {
        "running": False,
        "started_at": None,
        "finished_at": None,
        "current_document": None,
        "total_target": 0,
        "completed": 0,
        "failed": 0,
        "skipped": 0,
        "max_docs": settings.ingestion_max_docs,
        "tokens": {"prompt": 0, "completion": 0, "embedding": 0, "total": 0},
        "errors": [],          # list of {document_id, title, error, ts}
        "log": [],             # list of human-readable messages
        "last_run_summary": None,
    }


def _load() -> Dict[str, Any]:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _empty_state()


def _save(state: Dict[str, Any]) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_status() -> Dict[str, Any]:
    with _LOCK:
        return _load()


def is_running() -> bool:
    return get_status().get("running", False)


def begin_run(target_count: int, max_docs: int, mode: str) -> None:
    with _LOCK:
        state = _empty_state()
        state["running"] = True
        state["started_at"] = _now()
        state["total_target"] = target_count
        state["max_docs"] = max_docs
        state["log"].append(f"[{_now()}] Run started ({mode}). target={target_count} max_docs={max_docs}")
        _save(state)


def log(message: str) -> None:
    with _LOCK:
        state = _load()
        state["log"].append(f"[{_now()}] {message}")
        # Cap log length
        state["log"] = state["log"][-500:]
        _save(state)


def set_current(document_title: Optional[str]) -> None:
    with _LOCK:
        state = _load()
        state["current_document"] = document_title
        _save(state)


def add_tokens(prompt: int = 0, completion: int = 0, embedding: int = 0) -> None:
    with _LOCK:
        state = _load()
        t = state["tokens"]
        t["prompt"] += prompt
        t["completion"] += completion
        t["embedding"] += embedding
        t["total"] = t["prompt"] + t["completion"] + t["embedding"]
        _save(state)


def record_completed() -> None:
    with _LOCK:
        state = _load()
        state["completed"] += 1
        _save(state)


def record_skipped(reason: str) -> None:
    with _LOCK:
        state = _load()
        state["skipped"] += 1
        state["log"].append(f"[{_now()}] skipped: {reason}")
        _save(state)


def record_error(document_id: str, title: str, error: str) -> None:
    with _LOCK:
        state = _load()
        state["failed"] += 1
        state["errors"].append(
            {"document_id": document_id, "title": title, "error": error, "ts": _now()}
        )
        state["log"].append(f"[{_now()}] ERROR {title}: {error}")
        _save(state)


def end_run(summary: str) -> None:
    with _LOCK:
        state = _load()
        state["running"] = False
        state["finished_at"] = _now()
        state["current_document"] = None
        state["last_run_summary"] = summary
        state["log"].append(f"[{_now()}] {summary}")
        _save(state)


def reset() -> Dict[str, Any]:
    """Force the persisted status back to an idle/empty state.

    Use this to recover from a stuck `running: true` flag when a worker
    thread has died without calling `end_run` (e.g. container restart in
    the middle of a run, or a hung Document Intelligence poller).

    NOTE: This does NOT kill any worker thread that might still be alive
    in-process; it only clears the persisted state file. Pair it with a
    container restart if you suspect a zombie worker.
    """
    with _LOCK:
        state = _empty_state()
        state["log"].append(f"[{_now()}] Status reset via admin.")
        _save(state)
        return state
