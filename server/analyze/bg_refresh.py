"""
Best-effort background refresh executor.

Used to run slow, non-blocking refresh work after a job has already produced a fast fallback.
This work MUST NOT emit SSE events for the original job (SSE stops at job.completed).
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional


logger = logging.getLogger(__name__)

_executor: Optional[ThreadPoolExecutor] = None
_lock = threading.Lock()


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _enabled() -> bool:
    raw = os.getenv("DINQ_BG_REFRESH_ENABLED")
    if raw is None:
        return True
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _max_workers() -> int:
    val = _read_int_env("DINQ_BG_REFRESH_MAX_WORKERS", 2)
    return max(1, min(int(val), 16))


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is not None:
        return _executor
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=_max_workers(), thread_name_prefix="dinq-bg-refresh")
    return _executor


def submit(*, name: str, fn: Callable[[], None]) -> bool:
    """
    Submit a background refresh task.

    Returns False if disabled or submission fails.
    """

    if not _enabled():
        return False

    task_name = str(name or "").strip() or "bg_refresh"
    try:
        _get_executor().submit(_run_safe, task_name, fn)
        return True
    except Exception:
        return False


def _run_safe(name: str, fn: Callable[[], None]) -> None:
    try:
        fn()
    except Exception:
        logger.exception("Background refresh task failed: %s", name)
