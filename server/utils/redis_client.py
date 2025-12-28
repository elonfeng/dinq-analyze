"""Redis client utilities (optional dependency).

This module provides a tiny wrapper around redis-py so the codebase can:
- run without Redis (DB-only mode)
- use Redis for low-RTT realtime streaming/snapshots when configured

Enable by setting:
  DINQ_REDIS_URL=redis://127.0.0.1:6379/0
"""

from __future__ import annotations

import os
import threading
from typing import Any, Optional


_lock = threading.Lock()
_client: Any = None
_client_url: Optional[str] = None


def _redis_url() -> Optional[str]:
    url = (os.getenv("DINQ_REDIS_URL") or os.getenv("REDIS_URL") or "").strip()
    return url or None


def get_redis_client():
    """
    Return a process-global Redis client when configured, else None.

    Notes:
    - Import redis-py lazily to keep Redis optional in local/dev environments.
    - decode_responses=False to keep binary-safe behavior; callers can decode explicitly.
    """

    url = _redis_url()
    if not url:
        return None

    try:
        import redis  # type: ignore[import-not-found]
    except Exception:
        return None

    global _client, _client_url
    with _lock:
        if _client is not None and _client_url == url:
            return _client

        socket_timeout = float(os.getenv("DINQ_REDIS_SOCKET_TIMEOUT_SECONDS", "5") or "5")
        socket_connect_timeout = float(os.getenv("DINQ_REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", "2") or "2")
        _client = redis.Redis.from_url(
            url,
            decode_responses=False,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            health_check_interval=30,
        )
        _client_url = url
        return _client

