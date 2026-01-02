"""
Async replication from local SQLite cache -> remote backup DB (single-machine friendly).

This module implements an outbox pattern:
  - Writers (AnalysisCacheStore.save_*) enqueue (artifact_key, content_hash) into `analysis_backup_outbox`
  - A background replicator reads the outbox and upserts rows into the backup DB

Design goals:
  - Keep online requests SQLite-only (fast create + no SSE wait_job)
  - Make backup writes best-effort (never block the main path)
  - Deduplicate writes by (artifact_key, content_hash)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from src.models.db import AnalysisArtifactCache, AnalysisBackupOutbox
from src.utils.db_utils import backup_db_enabled, get_backup_db_session, get_cache_db_session


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


def _backup_ttl_multiplier() -> float:
    # Remote backup keeps artifacts longer by default.
    # You can override with DINQ_BACKUP_TTL_MULTIPLIER (e.g. 4 => 4x local TTL).
    return max(1.0, min(_read_float_env("DINQ_BACKUP_TTL_MULTIPLIER", 4.0), 365.0))


def _max_backup_ttl_seconds() -> int:
    # Cap to avoid "infinite" TTL growth from bugs. Default: 365 days.
    return max(0, min(_read_int_env("DINQ_BACKUP_MAX_TTL_SECONDS", 365 * 24 * 3600), 10 * 365 * 24 * 3600))


def _compute_backup_expires_at(*, created_at: datetime, expires_at: Optional[datetime]) -> Optional[datetime]:
    if expires_at is None or not isinstance(expires_at, datetime):
        return None
    if created_at is None or not isinstance(created_at, datetime):
        created_at = datetime.utcnow()

    ttl_s = max(0.0, (expires_at - created_at).total_seconds())
    if ttl_s <= 0.0:
        return expires_at

    mult = float(_backup_ttl_multiplier())
    boosted = ttl_s * mult
    cap = int(_max_backup_ttl_seconds())
    if cap > 0:
        boosted = min(float(cap), boosted)
    return created_at + timedelta(seconds=boosted)


def _json_size_bytes(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except Exception:
        return 0


@dataclass(frozen=True)
class _OutboxItem:
    id: int
    artifact_key: str
    kind: str
    content_hash: str
    retry_count: int


class BackupReplicator:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if not backup_db_enabled():
            return
        if not self._enabled():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="dinq-backup-replicator")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _enabled(self) -> bool:
        return _read_bool_env("DINQ_BACKUP_REPLICATOR_ENABLED", True)

    def _batch_size(self) -> int:
        return max(1, min(_read_int_env("DINQ_BACKUP_REPLICATOR_BATCH_SIZE", 50), 500))

    def _poll_interval_seconds(self) -> float:
        return max(0.05, min(_read_float_env("DINQ_BACKUP_REPLICATOR_POLL_SECONDS", 0.5), 10.0))

    def _lock_ttl_seconds(self) -> int:
        return max(5, min(_read_int_env("DINQ_BACKUP_REPLICATOR_LOCK_TTL_SECONDS", 120), 3600))

    def _max_payload_bytes(self) -> int:
        # Guardrail: prevent pushing huge blobs if backup DB has strict row limits.
        # 0 => no limit.
        return max(0, _read_int_env("DINQ_BACKUP_MAX_PAYLOAD_BYTES", 0))

    def _run_loop(self) -> None:
        # Fast fail: ensure backup DB is reachable.
        while not self._stop_event.is_set():
            try:
                with get_backup_db_session() as session:
                    session.execute(text("SELECT 1"))
                break
            except Exception as exc:
                logger.warning("backup db not ready, retrying: %s", str(exc)[:200])
                time.sleep(1.0)

        while not self._stop_event.is_set():
            try:
                processed = self._drain_once()
            except Exception as exc:  # noqa: BLE001
                logger.exception("backup replicator loop error: %s", exc)
                processed = 0
            if processed <= 0:
                time.sleep(self._poll_interval_seconds())

    def _claim_batch(self) -> List[_OutboxItem]:
        token = uuid.uuid4().hex
        now = datetime.utcnow()
        lock_expired_before = now - timedelta(seconds=int(self._lock_ttl_seconds()))
        limit = int(self._batch_size())

        try:
            with get_cache_db_session() as session:
                session.execute(
                    text(
                        "UPDATE analysis_backup_outbox "
                        "SET status='processing', lock_token=:token, locked_at=:now "
                        "WHERE id IN ("
                        "  SELECT id FROM analysis_backup_outbox "
                        "  WHERE ("
                        "    status='pending' "
                        "    OR (status='processing' AND locked_at IS NOT NULL AND locked_at <= :lock_expired_before)"
                        "  ) "
                        "    AND (next_retry_at IS NULL OR next_retry_at <= :now) "
                        "  ORDER BY id ASC "
                        "  LIMIT :limit"
                        ")"
                    ),
                    {
                        "token": token,
                        "now": now,
                        "lock_expired_before": lock_expired_before,
                        "limit": limit,
                    },
                )
                rows = (
                    session.query(AnalysisBackupOutbox)
                    .filter(
                        AnalysisBackupOutbox.status == "processing",
                        AnalysisBackupOutbox.lock_token == token,
                    )
                    .order_by(AnalysisBackupOutbox.id.asc())
                    .all()
                )
                out: List[_OutboxItem] = []
                for r in rows:
                    try:
                        out.append(
                            _OutboxItem(
                                id=int(r.id),
                                artifact_key=str(r.artifact_key or ""),
                                kind=str(r.kind or ""),
                                content_hash=str(r.content_hash or ""),
                                retry_count=int(r.retry_count or 0),
                            )
                        )
                    except Exception:
                        continue
                return out
        except Exception:
            return []

    def _load_local_artifact(self, *, artifact_key: str) -> Optional[AnalysisArtifactCache]:
        ak = str(artifact_key or "").strip()
        if not ak:
            return None
        try:
            with get_cache_db_session() as session:
                art = session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == ak).first()
                if art is None:
                    return None
                payload = art.payload if isinstance(getattr(art, "payload", None), dict) else None
                if not isinstance(payload, dict):
                    return None
                return AnalysisArtifactCache(
                    artifact_key=str(getattr(art, "artifact_key", "") or ""),
                    kind=str(getattr(art, "kind", "") or ""),
                    payload=payload,
                    content_hash=str(getattr(art, "content_hash", "") or "") or None,
                    created_at=getattr(art, "created_at", None),
                    expires_at=getattr(art, "expires_at", None),
                    meta=art.meta if isinstance(getattr(art, "meta", None), dict) else (art.meta or {}),
                )
        except Exception:
            return None

    def _upsert_backup_artifact(self, *, artifact: AnalysisArtifactCache) -> None:
        ak = str(getattr(artifact, "artifact_key", "") or "").strip()
        if not ak:
            raise ValueError("missing artifact_key")
        payload = getattr(artifact, "payload", None)
        if not isinstance(payload, dict) or not payload:
            raise ValueError("invalid payload for backup")

        created_at = getattr(artifact, "created_at", None)
        if created_at is None or not isinstance(created_at, datetime):
            created_at = datetime.utcnow()
        expires_at = getattr(artifact, "expires_at", None)
        backup_expires_at = _compute_backup_expires_at(created_at=created_at, expires_at=expires_at)

        meta = getattr(artifact, "meta", None)
        meta_out: Dict[str, Any] = dict(meta) if isinstance(meta, dict) else {}
        meta_out.setdefault("_backup", {})
        if isinstance(meta_out.get("_backup"), dict):
            meta_out["_backup"] = {
                **(meta_out.get("_backup") or {}),
                "replicated_at": datetime.utcnow().isoformat(),
            }

        max_bytes = int(self._max_payload_bytes())
        if max_bytes > 0 and _json_size_bytes(payload) > max_bytes:
            raise ValueError(f"payload too large for backup (>{max_bytes} bytes)")

        with get_backup_db_session() as session:
            existing = session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == ak).first()
            incoming_hash = str(getattr(artifact, "content_hash", "") or "")
            if existing is not None:
                current_hash = str(getattr(existing, "content_hash", "") or "")
                if incoming_hash and incoming_hash == current_hash:
                    # No meaningful change: don't touch payload (save bandwidth/IO).
                    return
                existing.kind = str(getattr(artifact, "kind", "") or existing.kind)
                existing.payload = payload
                existing.content_hash = incoming_hash or None
                existing.created_at = created_at
                existing.expires_at = backup_expires_at
                existing.meta = meta_out
                session.flush()
                return

            session.add(
                AnalysisArtifactCache(
                    artifact_key=ak,
                    kind=str(getattr(artifact, "kind", "") or ""),
                    payload=payload,
                    content_hash=incoming_hash or None,
                    created_at=created_at,
                    expires_at=backup_expires_at,
                    meta=meta_out,
                )
            )
            session.flush()

    def _mark_done(self, *, outbox_id: int) -> None:
        try:
            with get_cache_db_session() as session:
                session.query(AnalysisBackupOutbox).filter(AnalysisBackupOutbox.id == int(outbox_id)).delete()
        except Exception:
            return

    def _mark_retry(self, *, outbox_id: int, retry_count: int, error: str) -> None:
        now = datetime.utcnow()
        # Exponential backoff: 2^n seconds, capped.
        base = 2 ** max(0, min(int(retry_count), 10))
        delay_s = max(1, min(int(base), 3600))
        next_retry_at = now + timedelta(seconds=int(delay_s))

        try:
            with get_cache_db_session() as session:
                rec = session.query(AnalysisBackupOutbox).filter(AnalysisBackupOutbox.id == int(outbox_id)).first()
                if rec is None:
                    return
                rec.status = "pending"
                rec.retry_count = int(retry_count)
                rec.next_retry_at = next_retry_at
                rec.last_error = str(error or "")[:800]
                rec.lock_token = None
                rec.locked_at = None
                session.flush()
        except Exception:
            return

    def _drain_once(self) -> int:
        if not backup_db_enabled() or not self._enabled():
            return 0

        items = self._claim_batch()
        if not items:
            return 0

        processed = 0
        for item in items:
            if self._stop_event.is_set():
                break

            local = self._load_local_artifact(artifact_key=item.artifact_key)
            if local is None:
                self._mark_done(outbox_id=item.id)
                processed += 1
                continue

            try:
                self._upsert_backup_artifact(artifact=local)
                self._mark_done(outbox_id=item.id)
                processed += 1
            except Exception as exc:  # noqa: BLE001
                self._mark_retry(outbox_id=item.id, retry_count=int(item.retry_count) + 1, error=str(exc))

        return processed


_REPLICATOR: Optional[BackupReplicator] = None
_REPLICATOR_LOCK = threading.Lock()


def start_backup_replicator() -> None:
    """Idempotently start the background backup replicator (best-effort)."""
    global _REPLICATOR
    if _REPLICATOR is not None:
        try:
            _REPLICATOR.start()
        except Exception:
            pass
        return
    with _REPLICATOR_LOCK:
        if _REPLICATOR is not None:
            try:
                _REPLICATOR.start()
            except Exception:
                pass
            return
        _REPLICATOR = BackupReplicator()
        try:
            _REPLICATOR.start()
        except Exception:
            pass
