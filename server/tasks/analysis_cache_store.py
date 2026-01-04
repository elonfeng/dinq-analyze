"""
Cross-job analysis cache store (subjects / runs / artifact cache).

This is the backend foundation for:
- avoiding repeated expensive analysis for the same subject
- stale-while-revalidate (serve cached, refresh in background)
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError

from src.models.db import AnalysisArtifactCache, AnalysisRun, AnalysisSubject
from src.utils.db_utils import backup_db_enabled, get_backup_db_session, get_cache_db_session
from server.utils.sqlite_cache import get_sqlite_cache


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _dt_to_epoch_seconds(dt: Optional[datetime]) -> Optional[int]:
    if dt is None or not isinstance(dt, datetime):
        return None
    try:
        if dt.tzinfo is None:
            return int(dt.replace(tzinfo=timezone.utc).timestamp())
        return int(dt.timestamp())
    except Exception:
        return None


def _is_fallback_payload(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    meta = payload.get("_meta")
    if isinstance(meta, dict):
        if meta.get("fallback") or meta.get("is_fallback"):
            return True
    return False


def build_artifact_key(*, source: str, subject_key: str, pipeline_version: str, options_hash: str, kind: str) -> str:
    raw = json.dumps(
        {
            "source": str(source),
            "subject_key": str(subject_key),
            "pipeline_version": str(pipeline_version),
            "options_hash": str(options_hash),
            "kind": str(kind),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _sha256_hex(raw)


@dataclass(frozen=True)
class CachedRun:
    subject_id: int
    pipeline_version: str
    options_hash: str
    artifact_key: str
    created_at: Optional[datetime]
    expires_at: Optional[datetime]
    freshness_until: Optional[datetime]
    fingerprint: Optional[str]
    payload: Optional[Dict[str, Any]]


class AnalysisCacheStore:
    def _access_touch_throttle_seconds(self) -> int:
        """
        How frequently we update (last_access_at, hit_count) per artifact.

        Goal: enable LRU/hot-cold eviction without adding too much write overhead.
        """

        return 15

    def _payload_size_bytes(self, payload: Dict[str, Any]) -> int:
        try:
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except Exception:
            return 0
        return int(len(raw))

    def _merge_access_meta_on_write(
        self,
        *,
        existing_meta: Optional[Dict[str, Any]],
        incoming_meta: Optional[Dict[str, Any]],
        payload: Dict[str, Any],
        now: datetime,
    ) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        if isinstance(existing_meta, dict):
            merged.update(existing_meta)
        if isinstance(incoming_meta, dict):
            merged.update(incoming_meta)

        try:
            merged["hit_count"] = int(merged.get("hit_count") or 0)
        except Exception:
            merged["hit_count"] = 0

        now_utc = now.replace(tzinfo=timezone.utc)
        merged["last_access_at"] = now_utc.isoformat()
        merged["last_access_at_s"] = int(now_utc.timestamp())
        if "payload_size_bytes" not in merged:
            merged["payload_size_bytes"] = self._payload_size_bytes(payload)
        return merged

    def _maybe_touch_access_meta(self, *, session, artifact: AnalysisArtifactCache) -> None:  # type: ignore[no-untyped-def]
        """
        Best-effort: update last_access_at/hit_count for eviction.

        IMPORTANT: This must not raise or block callers on errors.
        """

        try:
            ak = str(getattr(artifact, "artifact_key", "") or "").strip()
        except Exception:
            ak = ""
        if not ak:
            return

        now_s = int(time.time())
        now_iso = datetime.utcfromtimestamp(now_s).replace(tzinfo=timezone.utc).isoformat()
        throttle_s = max(0, int(self._access_touch_throttle_seconds()))

        meta = getattr(artifact, "meta", None)
        if not isinstance(meta, dict):
            meta = {}

        last_s = 0
        try:
            last_s = int(meta.get("last_access_at_s") or 0)
        except Exception:
            last_s = 0

        if throttle_s > 0 and last_s > 0 and (now_s - last_s) < throttle_s:
            return

        try:
            hit_count = int(meta.get("hit_count") or 0) + 1
        except Exception:
            hit_count = 1

        meta["hit_count"] = int(hit_count)
        meta["last_access_at"] = now_iso
        meta["last_access_at_s"] = int(now_s)
        if "payload_size_bytes" not in meta:
            payload = getattr(artifact, "payload", None)
            if isinstance(payload, dict) and payload:
                meta["payload_size_bytes"] = self._payload_size_bytes(payload)

        artifact.meta = meta
        try:
            session.flush()
        except Exception:
            return

    def _backup_read_through_enabled(self) -> bool:
        """
        Whether cache reads should fall back to the remote backup DB when local cache misses.

        Default: enabled when a backup DB is configured.
        """

        import os

        if not backup_db_enabled():
            return False
        raw = str(os.getenv("DINQ_BACKUP_READ_THROUGH") or "true").strip().lower()
        return raw in ("1", "true", "yes", "on")

    def _enqueue_backup_outbox(self, *, session, artifact_key: str, kind: str, content_hash: str) -> None:  # type: ignore[no-untyped-def]
        """
        Best-effort: enqueue a replication task for the remote backup DB.

        IMPORTANT: Must not raise or poison the caller transaction.
        """

        if not backup_db_enabled():
            return

        ak = str(artifact_key or "").strip()
        k = str(kind or "").strip()
        ch = str(content_hash or "").strip()
        if not ak or not k or not ch:
            return

        try:
            # Deduplicate by (artifact_key, content_hash) so repeated writes don't flood the backup.
            session.execute(
                text(
                    "INSERT INTO analysis_backup_outbox(artifact_key, kind, content_hash, status, retry_count) "
                    "VALUES(:artifact_key, :kind, :content_hash, 'pending', 0) "
                    "ON CONFLICT(artifact_key, content_hash) DO NOTHING"
                ),
                {"artifact_key": ak, "kind": k, "content_hash": ch},
            )
        except Exception:
            return

    def _try_get_backup_artifact_cache(self, *, artifact_key: str) -> Optional[AnalysisArtifactCache]:
        if not self._backup_read_through_enabled():
            return None

        ak = str(artifact_key or "").strip()
        if not ak:
            return None

        try:
            with get_backup_db_session() as session:
                art = session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == ak).first()
                if art is None:
                    return None
                if not isinstance(getattr(art, "payload", None), dict):
                    return None
                # Detach from backup session.
                return AnalysisArtifactCache(
                    artifact_key=str(getattr(art, "artifact_key", "") or ""),
                    kind=str(getattr(art, "kind", "") or ""),
                    payload=art.payload,
                    content_hash=str(getattr(art, "content_hash", "") or "") or None,
                    created_at=getattr(art, "created_at", None),
                    expires_at=getattr(art, "expires_at", None),
                    meta=art.meta if isinstance(getattr(art, "meta", None), dict) else (art.meta or {}),
                )
        except Exception:
            return None

    def _rehydrate_local_artifact_cache(self, *, artifact: AnalysisArtifactCache) -> None:
        """
        Best-effort: write a backup artifact_cache row into the local cache DB.

        Must not enqueue replication again (avoid loops).
        """

        try:
            ak = str(getattr(artifact, "artifact_key", "") or "").strip()
            if not ak:
                return
            payload = getattr(artifact, "payload", None)
            if not isinstance(payload, dict) or not payload:
                return

            with get_cache_db_session() as session:
                existing = session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == ak).first()
                if existing is None:
                    now = datetime.utcnow()
                    session.add(
                        AnalysisArtifactCache(
                            artifact_key=ak,
                            kind=str(getattr(artifact, "kind", "") or ""),
                            payload=payload,
                            content_hash=str(getattr(artifact, "content_hash", "") or "") or None,
                            created_at=getattr(artifact, "created_at", None) or now,
                            expires_at=getattr(artifact, "expires_at", None),
                            meta=self._merge_access_meta_on_write(
                                existing_meta=None,
                                incoming_meta=getattr(artifact, "meta", None) if isinstance(getattr(artifact, "meta", None), dict) else {},
                                payload=payload,
                                now=now,
                            ),
                        )
                    )
                else:
                    incoming_hash = str(getattr(artifact, "content_hash", "") or "")
                    current_hash = str(getattr(existing, "content_hash", "") or "")
                    if incoming_hash and incoming_hash != current_hash:
                        existing.kind = str(getattr(artifact, "kind", "") or existing.kind)
                        existing.payload = payload
                        existing.content_hash = incoming_hash
                        existing.created_at = getattr(artifact, "created_at", None) or getattr(existing, "created_at", None) or datetime.utcnow()
                        existing.expires_at = getattr(artifact, "expires_at", None)
                        existing.meta = self._merge_access_meta_on_write(
                            existing_meta=existing.meta if isinstance(getattr(existing, "meta", None), dict) else {},
                            incoming_meta=getattr(artifact, "meta", None) if isinstance(getattr(artifact, "meta", None), dict) else {},
                            payload=payload,
                            now=datetime.utcnow(),
                        )
                    else:
                        # Even if payload is unchanged, this read-through should still count as an access.
                        try:
                            self._maybe_touch_access_meta(session=session, artifact=existing)
                        except Exception:
                            pass
                session.flush()
        except Exception:
            return

    def _refresh_lock_ttl_seconds(self) -> int:
        """
        How long a "running" refresh lock is considered valid.

        This protects against a crashed worker leaving a stuck running run that blocks all refreshes.
        """

        try:
            import os

            raw = os.getenv("DINQ_ANALYZE_REFRESH_LOCK_TTL_SECONDS", "900")
            ttl = int(raw or "900")
        except Exception:
            ttl = 900
        return max(60, min(int(ttl), 24 * 3600))

    def get_or_create_subject(
        self,
        *,
        source: str,
        subject_key: str,
        canonical_input: Optional[Dict[str, Any]] = None,
    ) -> AnalysisSubject:
        src = (source or "").strip().lower()
        key = (subject_key or "").strip()
        if not src or not key:
            raise ValueError("missing source/subject_key")

        with get_cache_db_session() as session:
            subject = (
                session.query(AnalysisSubject)
                .filter(AnalysisSubject.source == src, AnalysisSubject.subject_key == key)
                .first()
            )
            if subject is not None:
                if canonical_input and not getattr(subject, "canonical_input", None):
                    subject.canonical_input = canonical_input
                # updated_at is handled by onupdate if configured; set explicitly for safety.
                try:
                    subject.updated_at = datetime.utcnow()
                except Exception:
                    pass
                session.flush()
                session.refresh(subject)
                return subject

            subject = AnalysisSubject(
                source=src,
                subject_key=key,
                canonical_input=canonical_input or {},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(subject)
            session.flush()
            session.refresh(subject)
            return subject

    def try_begin_refresh_run(
        self,
        *,
        subject_id: int,
        pipeline_version: str,
        options_hash: str,
        fingerprint: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Best-effort global refresh dedupe.

        Returns True only for the first caller that successfully creates a "running" run row
        for the given (subject_id, pipeline_version, options_hash) key.
        """

        now = datetime.utcnow()
        lock_ttl = self._refresh_lock_ttl_seconds()

        with get_cache_db_session() as session:
            running = (
                session.query(AnalysisRun)
                .filter(
                    AnalysisRun.subject_id == int(subject_id),
                    AnalysisRun.pipeline_version == str(pipeline_version),
                    AnalysisRun.options_hash == str(options_hash),
                    AnalysisRun.status == "running",
                )
                .order_by(AnalysisRun.id.desc())
                .first()
            )
            if running is not None:
                started_at = getattr(running, "started_at", None) or getattr(running, "created_at", None) or now
                age = max(0.0, (now - started_at).total_seconds()) if isinstance(started_at, datetime) else 0.0
                if age > float(lock_ttl):
                    # Stale lock: mark failed so a new refresh can start.
                    running.status = "failed"
                    running.ended_at = now
                    running.meta = {**(running.meta or {}), "reason": "lock_expired", "lock_age_seconds": age}
                    session.flush()
                else:
                    return False

            try:
                session.add(
                    AnalysisRun(
                        subject_id=int(subject_id),
                        pipeline_version=str(pipeline_version),
                        options_hash=str(options_hash),
                        status="running",
                        fingerprint=fingerprint,
                        created_at=now,
                        started_at=now,
                        ended_at=None,
                        freshness_until=None,
                        meta=meta or {},
                    )
                )
                session.flush()
                return True
            except IntegrityError:
                # Another worker inserted concurrently (unique partial index on running).
                session.rollback()
                return False

    def fail_refresh_run(
        self,
        *,
        subject_id: int,
        pipeline_version: str,
        options_hash: str,
        reason: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mark the latest running refresh run as failed (best-effort).

        This prevents refresh locks from blocking subsequent refresh attempts until TTL expiry.
        """

        now = datetime.utcnow()
        with get_cache_db_session() as session:
            run = (
                session.query(AnalysisRun)
                .filter(
                    AnalysisRun.subject_id == int(subject_id),
                    AnalysisRun.pipeline_version == str(pipeline_version),
                    AnalysisRun.options_hash == str(options_hash),
                    AnalysisRun.status == "running",
                )
                .order_by(AnalysisRun.id.desc())
                .first()
            )
            if run is None:
                return
            run.status = "failed"
            run.ended_at = now
            run.meta = {**(run.meta or {}), **(meta or {}), "reason": str(reason or "error")[:200]}
            session.flush()

    def get_latest_cached_full_report(
        self,
        *,
        subject_id: int,
        pipeline_version: str,
        options_hash: str,
    ) -> Optional[CachedRun]:
        with get_cache_db_session() as session:
            run = (
                session.query(AnalysisRun)
                .filter(
                    AnalysisRun.subject_id == int(subject_id),
                    AnalysisRun.pipeline_version == str(pipeline_version),
                    AnalysisRun.options_hash == str(options_hash),
                    AnalysisRun.status == "completed",
                )
                .order_by(func.coalesce(AnalysisRun.ended_at, AnalysisRun.created_at).desc(), AnalysisRun.id.desc())
                .first()
            )
            if run is None or not run.full_report_artifact_key:
                return None

            art = session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == run.full_report_artifact_key).first()
            if art is None:
                return None

            payload = art.payload if isinstance(art.payload, dict) else None
            if isinstance(payload, dict) and payload:
                try:
                    self._maybe_touch_access_meta(session=session, artifact=art)
                except Exception:
                    pass
            # Best-effort: populate SQLite L1 so cache hits can avoid DB.
            try:
                cache = get_sqlite_cache()
                if cache is not None and isinstance(payload, dict):
                    expires_at = getattr(art, "expires_at", None)
                    cache.set_json(
                        key=str(getattr(art, "artifact_key", "") or run.full_report_artifact_key),
                        value={
                            "kind": str(getattr(art, "kind", "") or "full_report"),
                            "payload": payload,
                            "created_at": (getattr(art, "created_at", None) or datetime.utcnow()).isoformat(),
                            "expires_at": expires_at.isoformat() if isinstance(expires_at, datetime) else None,
                            "fingerprint": getattr(run, "fingerprint", None),
                        },
                        expires_at_s=_dt_to_epoch_seconds(expires_at),
                    )
            except Exception:
                pass
            return CachedRun(
                subject_id=int(subject_id),
                pipeline_version=str(pipeline_version),
                options_hash=str(options_hash),
                artifact_key=str(art.artifact_key),
                created_at=getattr(art, "created_at", None),
                expires_at=getattr(art, "expires_at", None),
                freshness_until=getattr(run, "freshness_until", None),
                fingerprint=getattr(run, "fingerprint", None),
                payload=payload,
            )

    def get_cached_artifact(
        self,
        *,
        source: str,
        subject_key: str,
        pipeline_version: str,
        options_hash: str,
        kind: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a cached artifact payload by deterministic key (no AnalysisRun indirection).

        This is useful for caching individual expensive artifacts (e.g. a single LLM bundle)
        independently from full_report caching/SWR.
        """

        src = (source or "").strip().lower()
        key = (subject_key or "").strip()
        k = str(kind or "").strip()
        if not src or not key or not k:
            return None

        artifact_key = build_artifact_key(
            source=src,
            subject_key=key,
            pipeline_version=str(pipeline_version),
            options_hash=str(options_hash),
            kind=k,
        )

        now = datetime.utcnow()
        art: Optional[AnalysisArtifactCache] = None
        try:
            with get_cache_db_session() as session:
                art = session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == artifact_key).first()
                if art is not None:
                    expires_at = getattr(art, "expires_at", None)
                    if expires_at and isinstance(expires_at, datetime) and expires_at <= now:
                        session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == artifact_key).delete()
                        art = None
                    else:
                        try:
                            self._maybe_touch_access_meta(session=session, artifact=art)
                        except Exception:
                            pass
        except Exception:
            art = None

        if art is None:
            backup_art = self._try_get_backup_artifact_cache(artifact_key=str(artifact_key))
            if backup_art is None:
                return None
            expires_at = getattr(backup_art, "expires_at", None)
            if expires_at and isinstance(expires_at, datetime) and expires_at <= now:
                return None
            self._rehydrate_local_artifact_cache(artifact=backup_art)
            art = backup_art

        return art.payload if isinstance(getattr(art, "payload", None), dict) else None

    def get_cached_final_result(
        self,
        *,
        source: str,
        subject_key: str,
        pipeline_version: str,
        options_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a cached FINAL result by deterministic key.

        Important:
        - Unlike get_cached_artifact(), this does NOT delete expired rows.
          We intentionally serve stale content (SWR) and refresh in background.
        - Payload schema is:
            { "cards": { "<card_type>": <payload> } }
        """

        src = (source or "").strip().lower()
        key = (subject_key or "").strip()
        if not src or not key:
            return None

        artifact_key = build_artifact_key(
            source=src,
            subject_key=key,
            pipeline_version=str(pipeline_version),
            options_hash=str(options_hash),
            kind="final_result",
        )

        now = datetime.utcnow()
        art: Optional[AnalysisArtifactCache] = None
        try:
            with get_cache_db_session() as session:
                art = session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == artifact_key).first()
                if art is not None and isinstance(getattr(art, "payload", None), dict):
                    try:
                        self._maybe_touch_access_meta(session=session, artifact=art)
                    except Exception:
                        pass
        except Exception:
            art = None

        if art is None or not isinstance(getattr(art, "payload", None), dict):
            backup_art = self._try_get_backup_artifact_cache(artifact_key=str(artifact_key))
            if backup_art is None:
                return None
            self._rehydrate_local_artifact_cache(artifact=backup_art)
            art = backup_art

        expires_at = getattr(art, "expires_at", None)
        stale = bool(isinstance(expires_at, datetime) and expires_at <= now)
        payload = art.payload if isinstance(art.payload, dict) else None
        if not isinstance(payload, dict) or not isinstance(payload.get("cards"), dict) or not payload.get("cards"):
            return None

        # Best-effort: populate SQLite L1 so cache hits can avoid DB.
        try:
            cache = get_sqlite_cache()
            if cache is not None:
                cache.set_json(
                    key=str(artifact_key),
                    value={
                        "kind": "final_result",
                        "payload": payload,
                        "created_at": (getattr(art, "created_at", None) or now).isoformat(),
                        "expires_at": expires_at.isoformat() if isinstance(expires_at, datetime) else None,
                    },
                    expires_at_s=_dt_to_epoch_seconds(expires_at),
                )
        except Exception:
            pass

        return {
            "artifact_key": str(artifact_key),
            "payload": payload,
            "created_at": getattr(art, "created_at", None),
            "expires_at": expires_at,
            "stale": stale,
        }

    def save_cached_artifact(
        self,
        *,
        source: str,
        subject: AnalysisSubject,
        pipeline_version: str,
        options_hash: str,
        kind: str,
        payload: Dict[str, Any],
        ttl_seconds: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Save a cached artifact payload by deterministic key.

        Unlike save_full_report(), this does NOT update AnalysisRun rows; it's a lightweight
        cache for individual artifacts.
        """

        src = (source or "").strip().lower()
        k = str(kind or "").strip()
        if not src or not k or subject is None or not getattr(subject, "subject_key", None):
            raise ValueError("missing source/kind/subject")
        
        if _is_fallback_payload(payload):
            return ""

        now = datetime.utcnow()
        ttl = max(0, int(ttl_seconds or 0))
        expires_at = (now + timedelta(seconds=ttl)) if ttl else None

        artifact_key = build_artifact_key(
            source=src,
            subject_key=str(subject.subject_key),
            pipeline_version=str(pipeline_version),
            options_hash=str(options_hash),
            kind=k,
        )
        content_hash = _sha256_hex(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

        with get_cache_db_session() as session:
            art = session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == artifact_key).first()
            if art is None:
                art = AnalysisArtifactCache(
                    artifact_key=artifact_key,
                    kind=k,
                    payload=payload,
                    content_hash=content_hash,
                    created_at=now,
                    expires_at=expires_at,
                    meta=self._merge_access_meta_on_write(existing_meta=None, incoming_meta=meta or {}, payload=payload, now=now),
                )
                session.add(art)
            else:
                art.kind = k
                art.payload = payload
                art.content_hash = content_hash
                art.created_at = now
                art.expires_at = expires_at
                art.meta = self._merge_access_meta_on_write(existing_meta=art.meta or {}, incoming_meta=meta or {}, payload=payload, now=now)

            self._enqueue_backup_outbox(session=session, artifact_key=str(artifact_key), kind=str(k), content_hash=str(content_hash))
            session.flush()
            return artifact_key

    def save_full_report(
        self,
        *,
        source: str,
        subject: AnalysisSubject,
        pipeline_version: str,
        options_hash: str,
        fingerprint: Optional[str],
        payload: Dict[str, Any],
        ttl_seconds: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        if _is_fallback_payload(payload):
            return ""
        
        now = datetime.utcnow()
        ttl = max(0, int(ttl_seconds or 0))
        expires_at = (now + timedelta(seconds=ttl)) if ttl else None

        artifact_key = build_artifact_key(
            source=source,
            subject_key=subject.subject_key,
            pipeline_version=pipeline_version,
            options_hash=options_hash,
            kind="full_report",
        )

        content_hash = _sha256_hex(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

        with get_cache_db_session() as session:
            art = session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == artifact_key).first()
            if art is None:
                art = AnalysisArtifactCache(
                    artifact_key=artifact_key,
                    kind="full_report",
                    payload=payload,
                    content_hash=content_hash,
                    created_at=now,
                    expires_at=expires_at,
                    meta=self._merge_access_meta_on_write(existing_meta=None, incoming_meta=meta or {}, payload=payload, now=now),
                )
                session.add(art)
            else:
                art.kind = "full_report"
                art.payload = payload
                art.content_hash = content_hash
                art.created_at = now
                art.expires_at = expires_at
                art.meta = self._merge_access_meta_on_write(existing_meta=art.meta or {}, incoming_meta=meta or {}, payload=payload, now=now)

            self._enqueue_backup_outbox(session=session, artifact_key=str(artifact_key), kind="full_report", content_hash=str(content_hash))

            # If a refresh run is in progress, finalize it. Otherwise create a completed run record.
            running = (
                session.query(AnalysisRun)
                .filter(
                    AnalysisRun.subject_id == int(subject.id),
                    AnalysisRun.pipeline_version == str(pipeline_version),
                    AnalysisRun.options_hash == str(options_hash),
                    AnalysisRun.status == "running",
                )
                .order_by(AnalysisRun.id.desc())
                .first()
            )
            if running is not None:
                running.status = "completed"
                running.fingerprint = fingerprint
                running.full_report_artifact_key = artifact_key
                running.ended_at = now
                running.freshness_until = expires_at
                running.meta = meta or (running.meta or {})
            else:
                session.add(
                    AnalysisRun(
                        subject_id=subject.id,
                        pipeline_version=str(pipeline_version),
                        options_hash=str(options_hash),
                        status="completed",
                        fingerprint=fingerprint,
                        full_report_artifact_key=artifact_key,
                        created_at=now,
                        started_at=now,
                        ended_at=now,
                        freshness_until=expires_at,
                        meta=meta or {},
                    )
                )
            session.flush()

        # SQLite L1: store full_report snapshot for fast cache hits.
        try:
            cache = get_sqlite_cache()
            if cache is not None:
                cache.set_json(
                    key=str(artifact_key),
                    value={
                        "kind": "full_report",
                        "payload": payload,
                        "created_at": now.isoformat(),
                        "expires_at": expires_at.isoformat() if expires_at else None,
                        "fingerprint": fingerprint,
                    },
                    expires_at_s=_dt_to_epoch_seconds(expires_at),
                )
        except Exception:
            pass

        return artifact_key

    def save_final_result(
        self,
        *,
        source: str,
        subject: AnalysisSubject,
        pipeline_version: str,
        options_hash: str,
        payload: Dict[str, Any],
        ttl_seconds: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Save the FINAL (frontend-contract) card outputs for a subject.

        Payload schema:
          { "cards": { "<card_type>": <payload> } }

        This is the recommended cache target for "instant warm open", because it is:
        - much smaller than full_report
        - already normalized by the quality gate (internal=false cards)
        """

        src = (source or "").strip().lower()
        if not src or subject is None or not getattr(subject, "subject_key", None):
            raise ValueError("missing source/subject")
        if not isinstance(payload, dict) or not isinstance(payload.get("cards"), dict) or not payload.get("cards"):
            raise ValueError("invalid final_result payload (missing cards)")

        now = datetime.utcnow()
        ttl = max(0, int(ttl_seconds or 0))
        expires_at = (now + timedelta(seconds=ttl)) if ttl else None

        artifact_key = build_artifact_key(
            source=src,
            subject_key=str(subject.subject_key),
            pipeline_version=str(pipeline_version),
            options_hash=str(options_hash),
            kind="final_result",
        )
        content_hash = _sha256_hex(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

        # SQLite L1: store final_result snapshot for fast cache hits.
        # Speed-first: write L1 before L2 so user-visible warm opens can hit immediately even if the DB is high RTT.
        try:
            cache = get_sqlite_cache()
            if cache is not None:
                cache.set_json(
                    key=str(artifact_key),
                    value={
                        "kind": "final_result",
                        "payload": payload,
                        "created_at": now.isoformat(),
                        "expires_at": expires_at.isoformat() if expires_at else None,
                    },
                    expires_at_s=_dt_to_epoch_seconds(expires_at),
                )
        except Exception:
            pass

        with get_cache_db_session() as session:
            art = session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == artifact_key).first()
            if art is None:
                art = AnalysisArtifactCache(
                    artifact_key=artifact_key,
                    kind="final_result",
                    payload=payload,
                    content_hash=content_hash,
                    created_at=now,
                    expires_at=expires_at,
                    meta=self._merge_access_meta_on_write(existing_meta=None, incoming_meta=meta or {}, payload=payload, now=now),
                )
                session.add(art)
            else:
                art.kind = "final_result"
                art.payload = payload
                art.content_hash = content_hash
                art.created_at = now
                art.expires_at = expires_at
                art.meta = self._merge_access_meta_on_write(existing_meta=art.meta or {}, incoming_meta=meta or {}, payload=payload, now=now)

            self._enqueue_backup_outbox(session=session, artifact_key=str(artifact_key), kind="final_result", content_hash=str(content_hash))

            # Finalize a refresh run if one is in progress (SWR background refresh).
            running = (
                session.query(AnalysisRun)
                .filter(
                    AnalysisRun.subject_id == int(subject.id),
                    AnalysisRun.pipeline_version == str(pipeline_version),
                    AnalysisRun.options_hash == str(options_hash),
                    AnalysisRun.status == "running",
                )
                .order_by(AnalysisRun.id.desc())
                .first()
            )
            if running is not None:
                running.status = "completed"
                running.ended_at = now
                running.freshness_until = expires_at
                running.meta = {
                    **(running.meta or {}),
                    **(meta or {}),
                    "cache_kind": "final_result",
                    "final_artifact_key": artifact_key,
                }
            session.flush()

        return artifact_key
