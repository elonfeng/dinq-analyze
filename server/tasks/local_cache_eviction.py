"""
Local cache eviction for analysis artifacts (single-machine friendly).

This module periodically evicts rows in `analysis_artifact_cache` to keep the local SQLite cache
bounded by:
  - disk-size-based budget (auto)
  - TTL (expires_at + grace)
  - hot/cold signals (meta.hit_count + meta.last_access_at)

Design goals:
  - Best-effort: must not break online requests
  - Low ops burden: sane defaults, env vars are optional overrides
  - No multi-machine coordination assumptions
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine.url import make_url

from src.models.db import AnalysisArtifactCache
from src.utils.db_utils import CACHE_DB_URL, cache_engine, get_cache_db_session


logger = logging.getLogger(__name__)


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _read_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _is_sqlite_file_db(db_url: str) -> Tuple[bool, Optional[str]]:
    url = str(db_url or "").strip()
    if not url:
        return False, None
    try:
        u = make_url(url)
    except Exception:
        return False, None
    if not str(getattr(u, "drivername", "") or "").startswith("sqlite"):
        return False, None
    db = str(getattr(u, "database", "") or "").strip()
    if not db or db == ":memory:":
        return False, None
    return True, os.path.abspath(db)


def _disk_budget_bytes(db_path: str) -> int:
    """
    Compute a conservative cache budget from the disk size.

    Default policy (no env required):
      - target = 1% of disk total
      - min = 64 MiB
      - max = 10 GiB
      - cap further to <= 50% of currently free space
    """

    # Optional override: hard cap in bytes.
    override = _read_int_env("DINQ_CACHE_EVICTOR_MAX_BYTES", 0)
    if override and int(override) > 0:
        return max(16 * 1024 * 1024, int(override))

    try:
        usage = shutil.disk_usage(os.path.dirname(db_path) or ".")
        total = int(getattr(usage, "total", 0) or 0)
        free = int(getattr(usage, "free", 0) or 0)
    except Exception:
        total = 0
        free = 0

    min_b = 64 * 1024 * 1024
    max_b = 10 * 1024 * 1024 * 1024

    if total <= 0:
        # Fallback when disk usage isn't available (e.g. sandbox quirks).
        return 512 * 1024 * 1024

    target = int(float(total) * 0.01)
    target = max(min_b, min(max_b, target))

    if free > 0:
        target = min(target, int(float(free) * 0.5))
        target = max(16 * 1024 * 1024, target)

    return int(target)


def _cache_db_file_size_bytes(db_path: str) -> int:
    total = 0
    for suffix in ("", "-wal", "-shm"):
        p = f"{db_path}{suffix}"
        try:
            total += int(os.path.getsize(p))
        except Exception:
            continue
    return int(total)


def _normalize_meta(meta: Any) -> Dict[str, Any]:
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str) and meta.strip():
        try:
            obj = json.loads(meta)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _int_from_meta(meta: Dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(meta.get(key) or default)
    except Exception:
        return int(default)


@dataclass(frozen=True)
class _Candidate:
    artifact_key: str
    created_at_s: int
    expires_at_s: Optional[int]
    last_access_at_s: int
    hit_count: int
    payload_size_bytes: int


class LocalCacheEvictor:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        is_sqlite, path = _is_sqlite_file_db(str(CACHE_DB_URL or "").strip())
        self._enabled = bool(is_sqlite and path and cache_engine.dialect.name == "sqlite")
        self._db_path = path

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if not self._enabled:
            return
        if not self._feature_enabled():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="dinq-local-cache-evictor")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _feature_enabled(self) -> bool:
        return _read_bool_env("DINQ_CACHE_EVICTOR_ENABLED", True)

    def _poll_interval_seconds(self) -> float:
        return max(5.0, min(_read_float_env("DINQ_CACHE_EVICTOR_INTERVAL_SECONDS", 60.0), 3600.0))

    def _expired_grace_seconds(self) -> int:
        # Keep stale rows for a while (SWR), but don't keep forever.
        return max(0, min(_read_int_env("DINQ_CACHE_EVICTOR_STALE_GRACE_SECONDS", 24 * 3600), 30 * 24 * 3600))

    def _delete_batch_size(self) -> int:
        return max(50, min(_read_int_env("DINQ_CACHE_EVICTOR_BATCH_SIZE", 500), 5000))

    def _run_loop(self) -> None:
        # Small initial delay: let the server finish startup and avoid contention.
        time.sleep(1.0)
        while not self._stop_event.is_set():
            try:
                self.evict_once()
            except Exception as exc:  # noqa: BLE001
                logger.exception("local cache eviction error: %s", exc)
            time.sleep(self._poll_interval_seconds())

    def evict_once(self) -> None:
        if not self._enabled or not self._db_path:
            return

        budget = int(_disk_budget_bytes(self._db_path))
        if budget <= 0:
            return

        now = datetime.utcnow()
        grace_s = int(self._expired_grace_seconds())
        expired_before = now - timedelta(seconds=grace_s) if grace_s > 0 else now

        deleted_expired = 0
        try:
            deleted_expired = self._delete_expired_batch(expired_before=expired_before)
        except Exception:
            deleted_expired = 0

        # Fast path: if the DB file is small, skip heavier scans.
        try:
            size_bytes = _cache_db_file_size_bytes(self._db_path)
        except Exception:
            size_bytes = 0

        # We still evict by logical payload budget, but this heuristic avoids scanning on small DBs.
        if size_bytes > 0 and size_bytes <= int(budget * 0.9) and deleted_expired <= 0:
            return

        try:
            self._evict_by_budget(budget_bytes=budget)
        except Exception:
            return

    def _delete_expired_batch(self, *, expired_before: datetime) -> int:
        if expired_before is None or not isinstance(expired_before, datetime):
            return 0
        limit = int(self._delete_batch_size())
        if limit <= 0:
            return 0
        with get_cache_db_session() as session:
            res = session.execute(
                text(
                    "DELETE FROM analysis_artifact_cache WHERE artifact_key IN ("  # noqa: S608
                    "  SELECT artifact_key FROM analysis_artifact_cache "
                    "  WHERE expires_at IS NOT NULL AND expires_at <= :expired_before "
                    "  ORDER BY expires_at ASC "
                    "  LIMIT :limit"
                    ")"
                ),
                {"expired_before": expired_before, "limit": limit},
            )
            try:
                session.execute(text("PRAGMA wal_checkpoint(TRUNCATE);"))
            except Exception:
                pass
            try:
                return int(getattr(res, "rowcount", 0) or 0)
            except Exception:
                return 0

    def _load_candidates(self) -> List[_Candidate]:
        now_s = int(time.time())
        out: List[_Candidate] = []
        with get_cache_db_session() as session:
            rows = (
                session.query(
                    AnalysisArtifactCache.artifact_key,
                    AnalysisArtifactCache.created_at,
                    AnalysisArtifactCache.expires_at,
                    AnalysisArtifactCache.meta,
                )
                .all()
            )
        for artifact_key, created_at, expires_at, meta in rows:
            ak = str(artifact_key or "").strip()
            if not ak:
                continue
            m = _normalize_meta(meta)

            created_at_s = 0
            try:
                if isinstance(created_at, datetime):
                    if created_at.tzinfo is None:
                        created_at_s = int(created_at.replace(tzinfo=timezone.utc).timestamp())
                    else:
                        created_at_s = int(created_at.timestamp())
            except Exception:
                created_at_s = 0
            if created_at_s <= 0:
                created_at_s = now_s

            expires_at_s: Optional[int]
            try:
                if isinstance(expires_at, datetime):
                    if expires_at.tzinfo is None:
                        expires_at_s = int(expires_at.replace(tzinfo=timezone.utc).timestamp())
                    else:
                        expires_at_s = int(expires_at.timestamp())
                else:
                    expires_at_s = None
            except Exception:
                expires_at_s = None

            last_access_at_s = _int_from_meta(m, "last_access_at_s", 0)
            if last_access_at_s <= 0:
                last_access_at_s = created_at_s

            hit_count = _int_from_meta(m, "hit_count", 0)
            payload_size_bytes = _int_from_meta(m, "payload_size_bytes", 0)
            if payload_size_bytes <= 0:
                # Conservative default for older rows that didn't have size metadata.
                payload_size_bytes = 64 * 1024

            out.append(
                _Candidate(
                    artifact_key=ak,
                    created_at_s=int(created_at_s),
                    expires_at_s=expires_at_s,
                    last_access_at_s=int(last_access_at_s),
                    hit_count=int(hit_count),
                    payload_size_bytes=int(payload_size_bytes),
                )
            )
        return out

    def _evict_by_budget(self, *, budget_bytes: int) -> None:
        budget = int(budget_bytes or 0)
        if budget <= 0:
            return

        candidates = self._load_candidates()
        if not candidates:
            return

        current_bytes = 0
        for c in candidates:
            current_bytes += max(1, int(c.payload_size_bytes))

        if current_bytes <= budget:
            return

        target_bytes = int(float(budget) * 0.8)
        to_free = max(1, current_bytes - max(0, target_bytes))
        now_s = int(time.time())

        # Evict cold first:
        #   - expired rows (even if within grace window)
        #   - low hit_count
        #   - oldest last_access_at
        def _sort_key(c: _Candidate) -> Tuple[int, int, int, int]:
            expired_flag = 0
            try:
                if c.expires_at_s is not None and int(c.expires_at_s) <= now_s:
                    expired_flag = 0
                else:
                    expired_flag = 1
            except Exception:
                expired_flag = 1
            return (
                int(expired_flag),
                int(c.hit_count),
                int(c.last_access_at_s),
                int(c.created_at_s),
            )

        candidates.sort(key=_sort_key)

        freed = 0
        keys: List[str] = []
        for c in candidates:
            keys.append(c.artifact_key)
            freed += max(1, int(c.payload_size_bytes))
            if freed >= to_free:
                break

        if not keys:
            return

        batch = int(self._delete_batch_size())
        if batch <= 0:
            batch = 200

        with get_cache_db_session() as session:
            for i in range(0, len(keys), batch):
                chunk = keys[i : i + batch]
                if not chunk:
                    continue
                session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key.in_(chunk)).delete(
                    synchronize_session=False
                )
            try:
                session.execute(text("PRAGMA wal_checkpoint(TRUNCATE);"))
            except Exception:
                pass
            session.flush()


_EVICTOR: Optional[LocalCacheEvictor] = None
_EVICTOR_LOCK = threading.Lock()


def start_local_cache_evictor() -> None:
    """Idempotently start the background local cache evictor (best-effort)."""
    global _EVICTOR
    if _EVICTOR is not None:
        try:
            _EVICTOR.start()
        except Exception:
            pass
        return
    with _EVICTOR_LOCK:
        if _EVICTOR is not None:
            try:
                _EVICTOR.start()
            except Exception:
                pass
            return
        _EVICTOR = LocalCacheEvictor()
        try:
            _EVICTOR.start()
        except Exception:
            pass
