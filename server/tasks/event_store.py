"""
DB-backed event store for analysis streaming and replay.
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, Generator, Optional

from sqlalchemy import func, text

from src.utils.db_utils import get_db_session
from src.models.db import AnalysisJob, AnalysisJobCard, AnalysisJobEvent
from server.tasks.job_store import JobStore
from server.tasks.output_schema import ensure_output_envelope
from server.utils.stream_protocol import create_event, format_stream_message
from server.utils.redis_client import get_redis_client


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def _read_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


# Default max events per DB fetch in the SSE loop (resume-friendly, avoids tiny polling batches).
_DEFAULT_SSE_BATCH_SIZE = 500
_SSE_BATCH_SIZE = max(1, min(_read_int_env("DINQ_ANALYZE_SSE_BATCH_SIZE", _DEFAULT_SSE_BATCH_SIZE), 5000))


class EventStore:
    def __init__(self) -> None:
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._redis = get_redis_client()
        self._redis_ttl_seconds = max(0, _read_int_env("DINQ_REDIS_JOB_TTL_SECONDS", 60 * 60 * 24))
        self._redis_max_events = max(0, _read_int_env("DINQ_REDIS_JOB_MAX_EVENTS", 0))
        self._cleanup_on_job_completed = _read_bool_env("DINQ_REDIS_CLEANUP_ON_JOB_COMPLETED", True)
        self._post_job_ttl_seconds = max(0, min(_read_int_env("DINQ_REDIS_POST_JOB_TTL_SECONDS", 120), 3600))

    def redis_enabled(self) -> bool:
        return self._redis is not None

    def bootstrap_job_started_realtime(self, *, job_id: str, source: str) -> None:
        """
        Best-effort: ensure a newly-created job has an initial `job.started` event in Redis.

        Why:
        - JobStore.create_job_bundle() writes `job.started` to the DB with seq=1.
        - In Redis realtime mode, SSE reads from Redis streams, so without a Redis `job.started` the client
          may wait until the first card emits an event (hurting tt_first_event).

        Safety:
        - Redis-only: never falls back to DB (avoids duplicate DB `job.started` events).
        - If another producer already started emitting events, we do nothing.
        """

        if self._redis is None:
            return
        if not job_id:
            return

        last_seq_key = self._redis_job_last_seq_key(job_id)
        try:
            raw = self._redis.get(last_seq_key)
            if raw is not None:
                return
        except Exception:
            # If Redis errors here, just skip bootstrapping; caller still has DB-backed job.started.
            return

        try:
            seq = int(self._redis.incr(last_seq_key))
        except Exception:
            return
        # Only bootstrap if this is the very first event.
        if seq != 1:
            return

        try:
            stream_key = self._redis_job_events_key(job_id)
            stream_id = f"{seq}-0"
            record = {
                "seq": int(seq),
                "event_type": "job.started",
                "card_id": None,
                "payload": {"job_id": job_id, "source": source},
            }
            body = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._redis.xadd(stream_key, {"v": body}, id=stream_id)
            if self._redis_ttl_seconds > 0:
                self._redis_touch_keys([stream_key, last_seq_key, self._redis_job_terminal_seq_key(job_id)])
        except Exception:
            # If stream write fails, keep going; worst case: job.started not in Redis (as before).
            return

    def _b64(self, value: str) -> str:
        raw = str(value or "")
        enc = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
        return enc.rstrip("=")

    def _b64d(self, value: str) -> str:
        raw = str(value or "")
        pad = "=" * (-len(raw) % 4)
        try:
            return base64.urlsafe_b64decode((raw + pad).encode("ascii")).decode("utf-8", errors="replace")
        except Exception:
            return raw

    def _redis_job_last_seq_key(self, job_id: str) -> str:
        return f"dinq:job:{job_id}:last_seq"

    def _redis_job_events_key(self, job_id: str) -> str:
        return f"dinq:job:{job_id}:events"

    def _redis_job_terminal_seq_key(self, job_id: str) -> str:
        return f"dinq:job:{job_id}:terminal_seq"

    def _redis_card_data_key(self, card_id: int) -> str:
        return f"dinq:card:{card_id}:data"

    def _redis_card_stream_formats_key(self, card_id: int) -> str:
        return f"dinq:card:{card_id}:stream_formats"

    def _redis_card_stream_sections_key(self, card_id: int) -> str:
        return f"dinq:card:{card_id}:stream_sections"

    def _redis_card_stream_text_key(self, card_id: int, field_enc: str, section_enc: str) -> str:
        return f"dinq:card:{card_id}:stream:{field_enc}:{section_enc}"

    def _redis_touch_keys(self, keys: list[str]) -> None:
        if not self._redis or not keys or self._redis_ttl_seconds <= 0:
            return
        try:
            pipe = self._redis.pipeline()
            for k in keys:
                pipe.expire(k, int(self._redis_ttl_seconds))
            pipe.execute()
        except Exception:
            return

    def _redis_unlink_or_delete(self, keys: list[Any]) -> None:
        if not self._redis or not keys:
            return
        try:
            pipe = self._redis.pipeline()
            # UNLINK is non-blocking (preferred) but may not exist on older Redis versions.
            if hasattr(self._redis, "unlink"):
                pipe.unlink(*keys)
            else:
                pipe.delete(*keys)
            pipe.execute()
        except Exception:
            return

    def _redis_cleanup_job_artifacts(self, job_id: str) -> None:
        if not self._redis or not job_id:
            return
        # ArtifactStore key format: dinq:artifact:{job_id}:{b64(type)}
        pattern = f"dinq:artifact:{job_id}:*"
        batch: list[Any] = []
        try:
            for k in self._redis.scan_iter(match=pattern, count=500):
                batch.append(k)
                if len(batch) >= 500:
                    self._redis_unlink_or_delete(batch)
                    batch = []
            if batch:
                self._redis_unlink_or_delete(batch)
        except Exception:
            return

    def _redis_set_post_job_ttl(self, job_id: str) -> None:
        if not self._redis or not job_id:
            return
        ttl = int(self._post_job_ttl_seconds or 0)
        if ttl <= 0:
            return
        try:
            pipe = self._redis.pipeline()
            pipe.expire(self._redis_job_events_key(job_id), ttl)
            pipe.expire(self._redis_job_last_seq_key(job_id), ttl)
            pipe.expire(self._redis_job_terminal_seq_key(job_id), ttl)
            pipe.execute()
        except Exception:
            return

    def _redis_apply_card_delta(self, *, card_id: int, payload: Dict[str, Any]) -> None:
        if not self._redis:
            return
        delta = payload.get("delta")
        if delta is None:
            return
        delta_text = str(delta)
        if not delta_text:
            return

        field = str(payload.get("field") or "content")
        section = str(payload.get("section") or "main")
        fmt = str(payload.get("format") or "markdown")

        field_enc = self._b64(field)
        section_enc = self._b64(section)

        text_key = self._redis_card_stream_text_key(card_id, field_enc, section_enc)
        formats_key = self._redis_card_stream_formats_key(card_id)
        sections_key = self._redis_card_stream_sections_key(card_id)
        member = f"{field_enc}:{section_enc}"

        try:
            pipe = self._redis.pipeline()
            pipe.append(text_key, delta_text)
            pipe.hset(formats_key, field_enc, fmt)
            pipe.sadd(sections_key, member)
            if self._redis_ttl_seconds > 0:
                pipe.expire(text_key, int(self._redis_ttl_seconds))
                pipe.expire(formats_key, int(self._redis_ttl_seconds))
                pipe.expire(sections_key, int(self._redis_ttl_seconds))
            pipe.execute()
        except Exception:
            return

    def _redis_apply_card_append(self, *, card_id: int, payload: Dict[str, Any]) -> None:
        if not self._redis:
            return
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return

        path = str(payload.get("path") or "items").strip()
        if path.startswith("data."):
            path = path[len("data."):]
        keys = [k for k in path.split(".") if k]
        if not keys:
            keys = ["items"]

        dedup_key = str(payload.get("dedup_key") or "id").strip()
        cursor = payload.get("cursor")
        partial = payload.get("partial")

        data_key = self._redis_card_data_key(card_id)

        # Use WATCH to avoid clobbering concurrent updates (append is low-frequency; safe to retry a few times).
        for _ in range(5):
            pipe = self._redis.pipeline()
            try:
                try:
                    pipe.watch(data_key)
                except Exception:
                    # WATCH may be disabled on some clients; fall back to best-effort overwrite.
                    pass

                raw = pipe.get(data_key)
                root = None
                if raw is not None:
                    try:
                        root = json.loads(raw.decode("utf-8"))
                    except Exception:
                        root = None
                if not isinstance(root, dict):
                    root = {}
                root = dict(root)

                parent: Dict[str, Any] = root
                for k in keys[:-1]:
                    cur = parent.get(k)
                    if not isinstance(cur, dict):
                        cur = {}
                    nxt = dict(cur)
                    parent[k] = nxt
                    parent = nxt

                leaf = keys[-1]
                existing = parent.get(leaf)
                if not isinstance(existing, list):
                    existing = []
                out = list(existing)

                seen: set[str] = set()
                if dedup_key:
                    for it in out:
                        if isinstance(it, dict) and it.get(dedup_key) is not None:
                            seen.add(str(it.get(dedup_key)))

                for it in items:
                    if dedup_key and isinstance(it, dict) and it.get(dedup_key) is not None:
                        key = str(it.get(dedup_key))
                        if key in seen:
                            continue
                        seen.add(key)
                    out.append(it)

                parent[leaf] = out

                if cursor is not None:
                    root["cursor"] = cursor
                if partial is not None:
                    root["partial"] = bool(partial)

                encoded = json.dumps(root, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

                try:
                    pipe.multi()
                except Exception:
                    pass
                pipe.set(data_key, encoded)
                if self._redis_ttl_seconds > 0:
                    pipe.expire(data_key, int(self._redis_ttl_seconds))
                pipe.execute()
                return
            except Exception as exc:
                msg = str(exc).lower()
                if "watch" in msg or "watchederror" in msg:
                    continue
                return
            finally:
                try:
                    pipe.reset()
                except Exception:
                    pass

    def _redis_set_card_output(self, *, card_id: int, output: Any) -> None:
        if not self._redis:
            return
        env = ensure_output_envelope(output)
        data = env.get("data")
        stream = env.get("stream")

        data_key = self._redis_card_data_key(card_id)
        try:
            encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except Exception:
            encoded = b"null"

        try:
            pipe = self._redis.pipeline()
            pipe.set(data_key, encoded)
            if self._redis_ttl_seconds > 0:
                pipe.expire(data_key, int(self._redis_ttl_seconds))
            pipe.execute()
        except Exception:
            return

        # If the caller provided a stream snapshot (rare), persist it too.
        if isinstance(stream, dict) and stream:
            try:
                for field, entry in stream.items():
                    if not isinstance(entry, dict):
                        continue
                    fmt = str(entry.get("format") or "markdown")
                    sections = entry.get("sections")
                    if not isinstance(sections, dict) or not sections:
                        continue
                    field_enc = self._b64(str(field))
                    formats_key = self._redis_card_stream_formats_key(card_id)
                    sections_key = self._redis_card_stream_sections_key(card_id)
                    for section, text_val in sections.items():
                        section_enc = self._b64(str(section))
                        text_key = self._redis_card_stream_text_key(card_id, field_enc, section_enc)
                        member = f"{field_enc}:{section_enc}"
                        text_str = str(text_val or "")
                        pipe = self._redis.pipeline()
                        pipe.set(text_key, text_str)
                        pipe.hset(formats_key, field_enc, fmt)
                        pipe.sadd(sections_key, member)
                        if self._redis_ttl_seconds > 0:
                            pipe.expire(text_key, int(self._redis_ttl_seconds))
                            pipe.expire(formats_key, int(self._redis_ttl_seconds))
                            pipe.expire(sections_key, int(self._redis_ttl_seconds))
                        pipe.execute()
            except Exception:
                return

    def get_card_output(self, *, card_id: int) -> Dict[str, Any]:
        """
        Fetch the best-effort card output envelope.

        - In DB mode: reads job_cards.output.
        - In Redis mode: reads Redis-maintained {data, stream} accumulated from events.
        """

        if not self._redis:
            with get_db_session() as session:
                card = session.query(AnalysisJobCard).filter(AnalysisJobCard.id == int(card_id)).first()
                if card is None:
                    return {"data": None, "stream": {}}
                return ensure_output_envelope(getattr(card, "output", None))

        data_key = self._redis_card_data_key(card_id)
        formats_key = self._redis_card_stream_formats_key(card_id)
        sections_key = self._redis_card_stream_sections_key(card_id)

        try:
            pipe = self._redis.pipeline()
            pipe.get(data_key)
            pipe.hgetall(formats_key)
            pipe.smembers(sections_key)
            raw_data, raw_formats, raw_members = pipe.execute()
        except Exception:
            # Fall back to DB mode if Redis is temporarily unavailable.
            try:
                with get_db_session() as session:
                    card = session.query(AnalysisJobCard).filter(AnalysisJobCard.id == int(card_id)).first()
                    if card is None:
                        return {"data": None, "stream": {}}
                    return ensure_output_envelope(getattr(card, "output", None))
            except Exception:
                return {"data": None, "stream": {}}

        data_obj = None
        if raw_data is not None:
            try:
                data_obj = json.loads(raw_data.decode("utf-8"))
            except Exception:
                data_obj = None

        formats: Dict[str, str] = {}
        if isinstance(raw_formats, dict):
            for k, v in raw_formats.items():
                try:
                    kk = k.decode("utf-8") if isinstance(k, (bytes, bytearray)) else str(k)
                    vv = v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)
                except Exception:
                    continue
                formats[kk] = vv

        members: list[str] = []
        if isinstance(raw_members, (set, list, tuple)):
            for m in raw_members:
                try:
                    mm = m.decode("utf-8") if isinstance(m, (bytes, bytearray)) else str(m)
                except Exception:
                    continue
                if mm:
                    members.append(mm)

        stream: Dict[str, Any] = {}
        if members:
            # Bulk GET all stream section strings.
            get_keys: list[str] = []
            pairs: list[tuple[str, str]] = []
            for token in members:
                if ":" not in token:
                    continue
                field_enc, section_enc = token.split(":", 1)
                pairs.append((field_enc, section_enc))
                get_keys.append(self._redis_card_stream_text_key(card_id, field_enc, section_enc))

            texts: list[Any] = []
            try:
                pipe2 = self._redis.pipeline()
                for k in get_keys:
                    pipe2.get(k)
                texts = pipe2.execute()
            except Exception:
                texts = []

            for (field_enc, section_enc), raw_text in zip(pairs, texts):
                field = self._b64d(field_enc)
                section = self._b64d(section_enc)
                text_val = ""
                if raw_text is not None:
                    try:
                        text_val = raw_text.decode("utf-8") if isinstance(raw_text, (bytes, bytearray)) else str(raw_text)
                    except Exception:
                        text_val = ""

                entry = stream.get(field)
                if not isinstance(entry, dict):
                    entry = {}
                entry = dict(entry)
                if entry.get("format") is None:
                    entry["format"] = formats.get(field_enc) or "markdown"
                sections = entry.get("sections")
                if not isinstance(sections, dict):
                    sections = {}
                sections = dict(sections)
                sections[section] = text_val
                entry["sections"] = sections
                stream[field] = entry

        return {"data": data_obj, "stream": stream}

    def get_card_outputs(self, *, card_ids: list[int]) -> Dict[int, Dict[str, Any]]:
        """
        Bulk variant of get_card_output() optimized for Redis mode.

        Why:
        - /api/analyze/jobs/<job_id> may contain many cards.
        - Fetching each card via get_card_output() causes many Redis round trips (and extra CPU for JSON decode).
        - This method pipelines Redis ops across cards and returns {card_id -> output_env}.
        """

        ids = [int(cid) for cid in (card_ids or []) if cid]
        if not ids:
            return {}

        # DB-only path: best-effort, used mainly in tests / fallback flows.
        if not self._redis:
            out: Dict[int, Dict[str, Any]] = {}
            with get_db_session() as session:
                rows = (
                    session.query(AnalysisJobCard.id, AnalysisJobCard.output)
                    .filter(AnalysisJobCard.id.in_(ids))
                    .all()
                )
                for cid, payload in rows:
                    try:
                        out[int(cid)] = ensure_output_envelope(payload)
                    except Exception:
                        continue
            return out

        # Redis path (pipelined across cards).
        try:
            pipe = self._redis.pipeline()
            for cid in ids:
                pipe.get(self._redis_card_data_key(int(cid)))
                pipe.hgetall(self._redis_card_stream_formats_key(int(cid)))
                pipe.smembers(self._redis_card_stream_sections_key(int(cid)))
            results = pipe.execute()
        except Exception:
            return {int(cid): {"data": None, "stream": {}} for cid in ids}

        # First pass: parse data + formats + members; collect all text keys for a second pipelined GET.
        out: Dict[int, Dict[str, Any]] = {}
        text_keys: list[str] = []
        key_meta: list[tuple[int, str, str, str]] = []
        #            (card_id, field_enc, section_enc, field_name)

        for idx, cid in enumerate(ids):
            base = idx * 3
            raw_data = results[base] if base < len(results) else None
            raw_formats = results[base + 1] if (base + 1) < len(results) else None
            raw_members = results[base + 2] if (base + 2) < len(results) else None

            data_obj = None
            if raw_data is not None:
                try:
                    data_obj = json.loads(raw_data.decode("utf-8")) if isinstance(raw_data, (bytes, bytearray)) else json.loads(str(raw_data))
                except Exception:
                    data_obj = None

            formats: Dict[str, str] = {}
            if isinstance(raw_formats, dict):
                for k, v in raw_formats.items():
                    try:
                        kk = k.decode("utf-8") if isinstance(k, (bytes, bytearray)) else str(k)
                        vv = v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)
                    except Exception:
                        continue
                    formats[kk] = vv

            members: list[str] = []
            if isinstance(raw_members, (set, list, tuple)):
                for m in raw_members:
                    try:
                        mm = m.decode("utf-8") if isinstance(m, (bytes, bytearray)) else str(m)
                    except Exception:
                        continue
                    if mm:
                        members.append(mm)

            stream: Dict[str, Any] = {}
            if members:
                for token in members:
                    if ":" not in token:
                        continue
                    field_enc, section_enc = token.split(":", 1)
                    field_name = self._b64d(field_enc)
                    text_key = self._redis_card_stream_text_key(int(cid), field_enc, section_enc)
                    text_keys.append(text_key)
                    key_meta.append((int(cid), field_enc, section_enc, field_name))

            out[int(cid)] = {"data": data_obj, "stream": stream, "_formats": formats}

        # Second pass: bulk get all stream text sections.
        if text_keys:
            try:
                pipe2 = self._redis.pipeline()
                for k in text_keys:
                    pipe2.get(k)
                raw_texts = pipe2.execute()
            except Exception:
                raw_texts = []

            for (cid, field_enc, section_enc, field_name), raw_text in zip(key_meta, raw_texts):
                env = out.get(int(cid))
                if not isinstance(env, dict):
                    continue
                formats = env.get("_formats")
                if not isinstance(formats, dict):
                    formats = {}
                stream = env.get("stream")
                if not isinstance(stream, dict):
                    stream = {}

                section_name = self._b64d(section_enc)
                text_val = ""
                if raw_text is not None:
                    try:
                        text_val = raw_text.decode("utf-8") if isinstance(raw_text, (bytes, bytearray)) else str(raw_text)
                    except Exception:
                        text_val = ""

                entry = stream.get(field_name)
                if not isinstance(entry, dict):
                    entry = {}
                entry = dict(entry)
                if entry.get("format") is None:
                    entry["format"] = str(formats.get(field_enc) or "markdown")

                sections = entry.get("sections")
                if not isinstance(sections, dict):
                    sections = {}
                sections = dict(sections)
                sections[section_name] = text_val
                entry["sections"] = sections
                stream[field_name] = entry
                env["stream"] = stream

        # Drop internal helper fields.
        cleaned: Dict[int, Dict[str, Any]] = {}
        for cid, env in out.items():
            if not isinstance(env, dict):
                continue
            cleaned[int(cid)] = {"data": env.get("data"), "stream": env.get("stream") if isinstance(env.get("stream"), dict) else {}}
        return cleaned

    def _dialect_name(self, session) -> str:  # type: ignore[no-untyped-def]
        try:
            bind = session.get_bind()
            name = getattr(getattr(bind, "dialect", None), "name", None) if bind is not None else None
            return str(name or "").strip().lower()
        except Exception:
            return ""

    def _lock_for_job(self, job_id: str) -> threading.Lock:
        with self._global_lock:
            lock = self._locks.get(job_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[job_id] = lock
            return lock

    def _next_seq(self, session, job_id: str) -> int:  # type: ignore[no-untyped-def]
        """
        Allocate the next monotonic seq for a job in a multi-process safe way.

        Strategy:
        - Prefer jobs.last_seq atomic increment so multiple gunicorn workers can safely append events.
        - Backward compat: if last_seq is missing/0, derive from MAX(job_events.seq) once.
        """

        # Fast path for Postgres: atomic increment avoids extra SELECT/refresh round trips which are very costly
        # when the DB is remote (high RTT).
        if self._dialect_name(session) == "postgresql":
            try:
                row = session.execute(
                    text(
                        "UPDATE jobs "
                        "SET last_seq = last_seq + 1, updated_at = NOW() "
                        "WHERE id = :job_id AND last_seq > 0 "
                        "RETURNING last_seq"
                    ),
                    {"job_id": job_id},
                ).first()
                if row and row[0] is not None:
                    return int(row[0])
            except Exception:
                # Fall back to the generic (row-lock) path below.
                pass

        q = session.query(AnalysisJob).filter(AnalysisJob.id == job_id)
        try:
            q = q.with_for_update()
        except Exception:  # noqa: BLE001
            pass
        job = q.first()

        if job is None:
            max_seq = (
                session.query(func.max(AnalysisJobEvent.seq))
                .filter(AnalysisJobEvent.job_id == job_id)
                .scalar()
            )
            return int(max_seq or 0) + 1

        try:
            last_seq = int(getattr(job, "last_seq", 0) or 0)
        except Exception:  # noqa: BLE001
            last_seq = 0

        if last_seq <= 0:
            max_seq = (
                session.query(func.max(AnalysisJobEvent.seq))
                .filter(AnalysisJobEvent.job_id == job_id)
                .scalar()
            )
            last_seq = int(max_seq or 0)

        next_seq = int(last_seq) + 1
        try:
            job.last_seq = next_seq
        except Exception:
            pass
        try:
            job.updated_at = datetime.utcnow()
        except Exception:
            pass
        return next_seq

    def append_event(
        self,
        *,
        job_id: str,
        card_id: Optional[int],
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> AnalysisJobEvent:
        payload = payload or {}
        if self._redis is not None:
            # Redis-backed realtime path (low-RTT). DB persistence is best-effort and can be handled separately.
            seq = 0
            try:
                seq = int(self._redis.incr(self._redis_job_last_seq_key(job_id)))
            except Exception:
                # If Redis is configured but unavailable, fall back to DB to avoid dropping all events.
                seq = 0

            if seq > 0:
                try:
                    if event_type == "card.delta" and card_id is not None:
                        self._redis_apply_card_delta(card_id=int(card_id), payload=payload)
                    elif event_type == "card.append" and card_id is not None:
                        self._redis_apply_card_append(card_id=int(card_id), payload=payload)
                    elif event_type in ("card.completed", "card.prefill") and card_id is not None:
                        env = ensure_output_envelope(payload.get("payload"))
                        self._redis_set_card_output(card_id=int(card_id), output=env)
                except Exception:
                    pass

                try:
                    stream_key = self._redis_job_events_key(job_id)
                    stream_id = f"{seq}-0"
                    record = {
                        "seq": seq,
                        "event_type": str(event_type),
                        "card_id": int(card_id) if card_id is not None else None,
                        "payload": payload,
                    }
                    body = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    if self._redis_max_events > 0:
                        self._redis.xadd(
                            stream_key,
                            {"v": body},
                            id=stream_id,
                            maxlen=int(self._redis_max_events),
                            approximate=True,
                        )
                    else:
                        self._redis.xadd(stream_key, {"v": body}, id=stream_id)
                    if str(event_type) == "job.completed":
                        self._redis.set(self._redis_job_terminal_seq_key(job_id), str(seq).encode("utf-8"))
                    if self._redis_ttl_seconds > 0:
                        self._redis_touch_keys(
                            [
                                stream_key,
                                self._redis_job_last_seq_key(job_id),
                                self._redis_job_terminal_seq_key(job_id),
                            ]
                        )
                except Exception:
                    pass

                # Best-effort durability: persist terminal job events into DB (low volume) so SSE can recover
                # even if Redis drops the terminal record (or job events are evicted).
                if str(event_type) in ("job.completed", "job.failed"):
                    try:
                        with get_db_session() as session:
                            try:
                                session.add(
                                    AnalysisJobEvent(
                                        job_id=job_id,
                                        card_id=int(card_id) if card_id is not None else None,
                                        seq=int(seq),
                                        event_type=str(event_type),
                                        payload=payload,
                                    )
                                )
                            except Exception:
                                pass
                            session.query(AnalysisJob).filter(AnalysisJob.id == job_id).update(
                                {"last_seq": int(seq), "updated_at": func.now()},
                                synchronize_session=False,
                            )
                    except Exception:
                        pass
                    # Best-effort cleanup: artifacts are only needed during job execution; delete once the job is terminal.
                    # Keep job events around briefly (post_job_ttl_seconds) to avoid SSE races for late readers.
                    if self._cleanup_on_job_completed:
                        try:
                            self._redis_set_post_job_ttl(job_id)
                            self._redis_cleanup_job_artifacts(job_id)
                        except Exception:
                            pass

                # Return a best-effort model instance for compatibility (not persisted).
                try:
                    return AnalysisJobEvent(job_id=job_id, card_id=card_id, seq=int(seq), event_type=event_type, payload=payload)
                except Exception:
                    return AnalysisJobEvent(job_id=job_id, card_id=card_id, seq=0, event_type=event_type, payload=payload)
        lock = self._lock_for_job(job_id)
        with lock:
            with get_db_session() as session:
                next_seq = self._next_seq(session, job_id)

                # Persist streaming deltas into job_cards.output so snapshots can show partial results.
                if event_type == "card.delta" and card_id is not None:
                    self._apply_card_delta(session, card_id=card_id, payload=payload)
                if event_type == "card.append" and card_id is not None:
                    self._apply_card_append(session, card_id=card_id, payload=payload)

                event = AnalysisJobEvent(
                    job_id=job_id,
                    card_id=card_id,
                    seq=next_seq,
                    event_type=event_type,
                    payload=payload,
                )
                session.add(event)
                # Avoid session.refresh(): it costs an extra DB round-trip and callers don't need it.
                return event

    def _apply_card_delta(self, session, *, card_id: int, payload: Dict[str, Any]) -> None:  # type: ignore[no-untyped-def]
        delta = payload.get("delta")
        if delta is None:
            return
        delta_text = str(delta)
        if not delta_text:
            return

        field = str(payload.get("field") or "content")
        section = str(payload.get("section") or "main")
        fmt = str(payload.get("format") or "markdown")

        q = session.query(AnalysisJobCard).filter(AnalysisJobCard.id == int(card_id))
        try:
            q = q.with_for_update()
        except Exception:  # noqa: BLE001
            pass
        card = q.first()
        if card is None:
            return

        # IMPORTANT: job_cards.output is a JSON column (non-mutable by default).
        # Avoid in-place mutations on nested dicts; SQLAlchemy won't reliably persist them.
        # Always assign a *new* object tree to ensure the change is detected and written.
        env = ensure_output_envelope(getattr(card, "output", None))
        data = env.get("data")

        prev_stream = env.get("stream")
        if not isinstance(prev_stream, dict):
            prev_stream = {}
        stream: Dict[str, Any] = dict(prev_stream)

        prev_entry = prev_stream.get(field)
        if not isinstance(prev_entry, dict):
            prev_entry = {}
        entry: Dict[str, Any] = dict(prev_entry)
        if entry.get("format") is None:
            entry["format"] = fmt

        prev_sections = prev_entry.get("sections")
        if not isinstance(prev_sections, dict):
            prev_sections = {}
        sections: Dict[str, Any] = dict(prev_sections)

        prev_text = str(sections.get(section) or "")
        sections[section] = prev_text + delta_text
        entry["sections"] = sections
        stream[field] = entry

        card.output = {"data": data, "stream": stream}
        try:
            card.updated_at = datetime.utcnow()
        except Exception:
            pass

    def _apply_card_append(self, session, *, card_id: int, payload: Dict[str, Any]) -> None:  # type: ignore[no-untyped-def]
        """
        Apply a structured "append" event into job_cards.output.data for snapshot-friendly list growth.

        Payload schema (best-effort):
          {
            "path": "items" | "data.items" | "<nested.path>",
            "items": [ ... ],
            "dedup_key": "id" (optional),
            "cursor": <any json> (optional),
            "partial": true/false (optional)
          }
        """

        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return

        path = str(payload.get("path") or "items").strip()
        if path.startswith("data."):
            path = path[len("data."):]
        keys = [k for k in path.split(".") if k]
        if not keys:
            keys = ["items"]

        dedup_key = str(payload.get("dedup_key") or "id").strip()
        cursor = payload.get("cursor")
        partial = payload.get("partial")

        q = session.query(AnalysisJobCard).filter(AnalysisJobCard.id == int(card_id))
        try:
            q = q.with_for_update()
        except Exception:  # noqa: BLE001
            pass
        card = q.first()
        if card is None:
            return

        env = ensure_output_envelope(getattr(card, "output", None))
        stream = env.get("stream")
        if not isinstance(stream, dict):
            stream = {}

        data = env.get("data")
        if not isinstance(data, dict):
            data = {}
        root: Dict[str, Any] = dict(data)

        parent: Dict[str, Any] = root
        for k in keys[:-1]:
            cur = parent.get(k)
            if not isinstance(cur, dict):
                cur = {}
            nxt = dict(cur)
            parent[k] = nxt
            parent = nxt

        leaf = keys[-1]
        existing = parent.get(leaf)
        if not isinstance(existing, list):
            existing = []
        out = list(existing)

        seen: set[str] = set()
        if dedup_key:
            for it in out:
                if isinstance(it, dict) and it.get(dedup_key) is not None:
                    seen.add(str(it.get(dedup_key)))

        for it in items:
            if dedup_key and isinstance(it, dict) and it.get(dedup_key) is not None:
                key = str(it.get(dedup_key))
                if key in seen:
                    continue
                seen.add(key)
            out.append(it)

        parent[leaf] = out

        if cursor is not None:
            root["cursor"] = cursor
        if partial is not None:
            root["partial"] = bool(partial)

        card.output = {"data": root, "stream": stream}
        try:
            card.updated_at = datetime.utcnow()
        except Exception:
            pass

    def fetch_events(self, job_id: str, after_seq: int, limit: int = _SSE_BATCH_SIZE) -> list[AnalysisJobEvent]:
        if self._redis is not None:
            stream_key = self._redis_job_events_key(job_id)
            min_id = f"{int(after_seq or 0) + 1}-0"
            try:
                rows = self._redis.xrange(stream_key, min=min_id, max="+", count=int(limit or _SSE_BATCH_SIZE))
            except Exception:
                rows = None

            if rows is not None:
                out: list[AnalysisJobEvent] = []
                for rid, fields in rows:
                    try:
                        rid_str = rid.decode("utf-8") if isinstance(rid, (bytes, bytearray)) else str(rid)
                        seq_str = rid_str.split("-", 1)[0]
                        seq = int(seq_str)
                    except Exception:
                        seq = 0

                    raw = None
                    if isinstance(fields, dict):
                        raw = fields.get(b"v") if b"v" in fields else fields.get("v")
                    if raw is None:
                        continue

                    try:
                        raw_str = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
                        rec = json.loads(raw_str)
                    except Exception:
                        continue

                    et = str(rec.get("event_type") or "")
                    payload = rec.get("payload") or {}
                    cid = rec.get("card_id")
                    try:
                        cid_int = int(cid) if cid is not None else None
                    except Exception:
                        cid_int = None

                    try:
                        out.append(AnalysisJobEvent(job_id=job_id, card_id=cid_int, seq=seq, event_type=et, payload=payload))
                    except Exception:
                        continue

                return out
        return self._fetch_events_db(job_id=job_id, after_seq=after_seq, limit=limit)

    def _fetch_events_db(self, *, job_id: str, after_seq: int, limit: int) -> list[AnalysisJobEvent]:
        with get_db_session() as session:
            return (
                session.query(AnalysisJobEvent)
                .filter(AnalysisJobEvent.job_id == job_id, AnalysisJobEvent.seq > int(after_seq or 0))
                .order_by(AnalysisJobEvent.seq.asc())
                .limit(int(limit or _SSE_BATCH_SIZE))
                .all()
            )

    def get_last_seq(self, job_id: str) -> int:
        if self._redis is not None:
            try:
                raw = self._redis.get(self._redis_job_last_seq_key(job_id))
                if raw is not None:
                    if isinstance(raw, (bytes, bytearray)):
                        raw = raw.decode("utf-8")
                    return int(raw or 0)
            except Exception:
                # Fall back to DB mode if Redis is temporarily unavailable.
                pass
        with get_db_session() as session:
            try:
                job = session.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
                if job is not None:
                    last_seq = int(getattr(job, "last_seq", 0) or 0)
                    if last_seq > 0:
                        return last_seq
            except Exception:
                pass
            max_seq = (
                session.query(func.max(AnalysisJobEvent.seq))
                .filter(AnalysisJobEvent.job_id == job_id)
                .scalar()
            )
            return int(max_seq or 0)

    def _redis_get_terminal_seq(self, job_id: str) -> Optional[int]:
        if self._redis is None:
            return None
        try:
            raw = self._redis.get(self._redis_job_terminal_seq_key(job_id))
            if raw is None:
                return None
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            val = int(raw or 0)
            return val if val > 0 else None
        except Exception:
            return None

    def stream_events(
        self,
        *,
        job_id: str,
        after_seq: int = 0,
        keepalive_seconds: float = 15.0,
        poll_interval: float = 0.5,
        stop_when_done: bool = False,
        job_store: Optional[JobStore] = None,
        terminal_grace_seconds: float = 1.0,
    ) -> Generator[str, None, None]:
        last_seq = int(after_seq or 0)
        last_activity = time.monotonic()
        terminal_states = {"completed", "partial", "failed", "cancelled"}
        # Stop SSE only after a job.completed event is streamed. (job.failed may still be emitted for diagnostics.)
        terminal_event_types = {"job.completed"}
        terminal_seq: Optional[int] = None
        terminal_status: Optional[str] = None
        last_terminal_check = 0.0
        saw_terminal_event = False

        def _refresh_terminal_seq() -> None:
            nonlocal terminal_seq, terminal_status, last_terminal_check
            if terminal_seq is not None:
                return

            # Fast path: Redis terminal marker.
            if self._redis is not None:
                terminal_seq = self._redis_get_terminal_seq(job_id)
                if terminal_seq is not None:
                    return

            # Fallback: if Redis keys were evicted/expired but DB status is terminal, allow SSE to stop.
            if job_store is None:
                return
            now = time.monotonic()
            if (now - last_terminal_check) < 2.0:
                return
            last_terminal_check = now
            try:
                job = job_store.get_job(job_id)
            except Exception:
                job = None
            if job is None:
                terminal_seq = last_seq
                return
            if getattr(job, "status", "") in terminal_states:
                terminal_status = str(getattr(job, "status", "") or "").strip().lower() or None
                # Best-effort: if DB also has terminal events (Redis outage runs), use them.
                try:
                    db_seq = self._get_terminal_seq(job_id, terminal_event_types=terminal_event_types)
                except Exception:
                    db_seq = None
                # If DB status is terminal but we never persisted a terminal event (rare but possible when the
                # DB write failed), force SSE to perform a one-shot fetch and then synthesize job.completed.
                terminal_seq = int(db_seq) if db_seq is not None else (int(last_seq) + 1)

        while True:
            events = self.fetch_events(job_id, after_seq=last_seq, limit=_SSE_BATCH_SIZE)
            if events:
                for ev in events:
                    last_seq = int(ev.seq or last_seq)
                    payload = ev.payload or {}
                    payload.setdefault("job_id", job_id)
                    payload.setdefault("seq", last_seq)
                    yield format_stream_message(
                        create_event(
                            source="analysis",
                            event_type=ev.event_type,
                            message="",
                            payload=payload,
                        )
                    )
                    last_activity = time.monotonic()
                    if ev.event_type in terminal_event_types:
                        terminal_seq = int(ev.seq or terminal_seq or last_seq)
                        saw_terminal_event = True
            else:
                if stop_when_done:
                    _refresh_terminal_seq()
                    # If Redis missed the terminal event, attempt a one-shot DB fetch to recover it and allow
                    # clients (and benches) to observe `job.completed`.
                    if terminal_seq is not None and last_seq < terminal_seq:
                        try:
                            db_events = self._fetch_events_db(job_id=job_id, after_seq=last_seq, limit=_SSE_BATCH_SIZE)
                        except Exception:
                            db_events = []
                        if db_events:
                            for ev in db_events:
                                last_seq = int(ev.seq or last_seq)
                                payload = ev.payload or {}
                                payload.setdefault("job_id", job_id)
                                payload.setdefault("seq", last_seq)
                                yield format_stream_message(
                                    create_event(
                                        source="analysis",
                                        event_type=ev.event_type,
                                        message="",
                                        payload=payload,
                                    )
                                )
                                last_activity = time.monotonic()
                                if ev.event_type in terminal_event_types:
                                    terminal_seq = int(ev.seq or terminal_seq or last_seq)
                                    saw_terminal_event = True
                            continue

                        # As a last resort, synthesize a terminal event so SSE can terminate cleanly.
                        if not saw_terminal_event and terminal_status is not None:
                            payload = {"job_id": job_id, "seq": int(terminal_seq), "status": terminal_status}
                            yield format_stream_message(
                                create_event(source="analysis", event_type="job.completed", message="", payload=payload)
                            )
                            last_seq = int(terminal_seq)
                            saw_terminal_event = True
                            break

                    if terminal_seq is not None and last_seq >= terminal_seq and (time.monotonic() - last_activity) >= float(terminal_grace_seconds or 0):
                        break
                time.sleep(poll_interval)

            if keepalive_seconds and (time.monotonic() - last_activity) >= keepalive_seconds:
                if stop_when_done:
                    _refresh_terminal_seq()
                    if terminal_seq is not None and last_seq >= terminal_seq:
                        break
                ping = create_event(
                    source="analysis",
                    event_type="ping",
                    message="",
                    step="keepalive",
                    legacy_type="ping",
                )
                ping.setdefault("content", "")
                yield format_stream_message(ping)
                last_activity = time.monotonic()

    def _get_terminal_seq(self, job_id: str, *, terminal_event_types: set[str]) -> Optional[int]:
        with get_db_session() as session:
            max_seq = (
                session.query(func.max(AnalysisJobEvent.seq))
                .filter(
                    AnalysisJobEvent.job_id == job_id,
                    AnalysisJobEvent.event_type.in_(tuple(terminal_event_types)),
                )
                .scalar()
            )
            if max_seq is None:
                return None
            try:
                return int(max_seq)
            except Exception:
                return None
