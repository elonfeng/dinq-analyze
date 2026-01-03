"""
Single-machine leader lock (cross-process).

Why:
- gunicorn runs multiple worker processes by default
- we must ensure only ONE process starts background loops that mutate SQLite
  (scheduler / cache evictor / backup replicator), otherwise:
    - SQLite lock contention increases
    - external API/LLM concurrency budgets multiply by worker count
    - cost/rate-limit risk increases

Design:
- Use a file lock (`fcntl.flock`) on a local lock file.
- Non-leader processes simply skip starting background loops.
- If the leader process dies, another process can take over (lock released by OS).
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional


logger = logging.getLogger(__name__)

try:
    import fcntl  # type: ignore
except Exception:  # noqa: BLE001
    fcntl = None  # type: ignore


_LOCK_FILES: Dict[str, object] = {}


def _lock_path(name: str) -> str:
    base = os.getenv("DINQ_LEADER_LOCK_DIR")
    if base is None or not str(base).strip():
        base = os.path.join(os.getcwd(), ".local", "locks")
    base = os.path.abspath(str(base))
    os.makedirs(base, exist_ok=True)
    safe = "".join([c for c in str(name or "default") if c.isalnum() or c in ("-", "_")]) or "default"
    return os.path.join(base, f"dinq_leader_{safe}.lock")


def is_leader(name: str = "background") -> bool:
    """
    Best-effort leader check for single-machine multi-process deployments.

    Returns True if this process holds the leader lock for `name`.
    """

    key = str(name or "background")
    if key in _LOCK_FILES:
        return True

    # Non-POSIX platforms: best-effort single-process assumption.
    if fcntl is None:
        _LOCK_FILES[key] = object()
        return True

    path = _lock_path(key)
    try:
        fp = open(path, "a+", encoding="utf-8")  # noqa: PTH123
    except Exception as exc:  # noqa: BLE001
        logger.warning("leader lock open failed (path=%s): %s", path, str(exc)[:200])
        return False

    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        try:
            fp.close()
        except Exception:
            pass
        return False
    except Exception as exc:  # noqa: BLE001
        try:
            fp.close()
        except Exception:
            pass
        logger.warning("leader lock acquire failed (path=%s): %s", path, str(exc)[:200])
        return False

    try:
        fp.seek(0)
        fp.truncate()
        fp.write(str(os.getpid()))
        fp.flush()
    except Exception:
        pass

    # Keep the file descriptor open for the lifetime of the process.
    _LOCK_FILES[key] = fp
    logger.info("leader lock acquired: %s (pid=%s)", path, os.getpid())
    return True


def leader_name_for_scheduler() -> str:
    return "scheduler"


def leader_name_for_cache_eviction() -> str:
    return "cache_eviction"


def leader_name_for_backup_replicator() -> str:
    return "backup_replicator"

