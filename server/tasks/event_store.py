"""
DB-backed event store for analysis streaming and replay.

All events are persisted to the SQL database and streamed to clients via SSE by polling
`job_events` in sequence order.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, Generator, Optional

from sqlalchemy import func
from sqlalchemy import text

from src.utils.db_utils import get_db_session
from src.models.db import AnalysisJob, AnalysisJobCard, AnalysisJobEvent
from server.tasks.event_bus import BusEvent, get_event_bus
from server.tasks.nats_backplane import get_nats_backplane
from server.tasks.job_store import JobStore
from server.tasks.output_schema import ensure_output_envelope
from server.utils.stream_protocol import create_event, format_stream_message


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


# Default max events per DB fetch in the SSE loop (resume-friendly, avoids tiny polling batches).
_DEFAULT_SSE_BATCH_SIZE = 500
_SSE_BATCH_SIZE = max(1, min(_read_int_env("DINQ_ANALYZE_SSE_BATCH_SIZE", _DEFAULT_SSE_BATCH_SIZE), 5000))


class EventStore:
    def __init__(self) -> None:
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        # Best-effort: start cross-process backplane (if enabled).
        try:
            get_nats_backplane()
        except Exception:
            pass

    def _dialect_name(self, session) -> str:  # type: ignore[no-untyped-def]
        try:
            bind = session.get_bind()
            name = getattr(getattr(bind, "dialect", None), "name", None) if bind is not None else None
            return str(name or "").strip().lower()
        except Exception:
            return ""

    def _lock_for_job(self, job_id: str) -> threading.Lock:
        jid = str(job_id or "")
        with self._global_lock:
            lock = self._locks.get(jid)
            if lock is None:
                lock = threading.Lock()
                self._locks[jid] = lock
            return lock

    def _sse_bus_mode(self) -> str:
        """
        Controls whether /stream uses the in-memory push bus.

        Env:
          DINQ_ANALYZE_SSE_BUS_MODE=auto|on|off

        Notes:
        - "auto" enables the bus only in in-process execution (local/dev).
        - External runner / multi-process setups should keep DB replay/polling.
        """

        return str(os.getenv("DINQ_ANALYZE_SSE_BUS_MODE") or "auto").strip().lower()

    def _use_event_bus_for_stream(self) -> bool:
        mode = self._sse_bus_mode()
        if mode in ("0", "false", "off", "disable", "disabled", "no"):
            return False
        if mode in ("1", "true", "on", "enable", "enabled", "yes"):
            return True
        # auto
        try:
            from server.config.executor_mode import get_executor_mode

            return get_executor_mode() == "inprocess"
        except Exception:
            return False

    def _publish_to_bus_best_effort(
        self,
        *,
        job_id: str,
        seq: int,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        try:
            p = dict(payload or {})
            p.setdefault("job_id", str(job_id))
            p.setdefault("seq", int(seq or 0))
            msg = format_stream_message(
                create_event(
                    source="analysis",
                    event_type=str(event_type),
                    message="",
                    payload=p,
                )
            )
            get_event_bus().publish(
                BusEvent(
                    job_id=str(job_id),
                    seq=int(seq or 0),
                    event_type=str(event_type),
                    message=str(msg),
                )
            )
            bp = get_nats_backplane()
            if bp is not None:
                bp.publish(
                    BusEvent(
                        job_id=str(job_id),
                        seq=int(seq or 0),
                        event_type=str(event_type),
                        message=str(msg),
                    )
                )
        except Exception:
            return

    def _next_seq(self, session, job_id: str) -> int:  # type: ignore[no-untyped-def]
        # IMPORTANT:
        # - Multiple schedulers/workers may append events concurrently for the same job.
        # - `seq` must be unique per (job_id, seq), so we must allocate it atomically in DB.

        dialect = self._dialect_name(session)

        # Fast path: single UPDATE ... RETURNING round trip.
        # - Postgres: reliable cross-process atomic increment.
        # - SQLite (>= 3.35): RETURNING is supported and helps shared-file multi-process runners.
        if dialect in ("postgresql", "sqlite"):
            updated_at_expr = "now()" if dialect == "postgresql" else "CURRENT_TIMESTAMP"
            try:
                row = session.execute(
                    text(
                        "UPDATE jobs "
                        f"SET last_seq = COALESCE(last_seq, 0) + 1, updated_at = {updated_at_expr} "
                        "WHERE id = :job_id "
                        "RETURNING last_seq"
                    ),
                    {"job_id": str(job_id)},
                ).first()
                if row is not None:
                    try:
                        return int(getattr(row, "last_seq", None) or row[0])
                    except Exception:
                        return int(row[0])
            except Exception:
                # Fall back to the generic ORM path below.
                pass

        # Generic path: lock the job row, then increment in one transaction.
        q = session.query(AnalysisJob).filter(AnalysisJob.id == job_id)
        try:
            q = q.with_for_update()
        except Exception:  # noqa: BLE001
            pass
        job = q.first()

        if job is None:
            # Should not happen for valid jobs, but keep seq monotonic for safety.
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
        job.last_seq = next_seq
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
        lock = self._lock_for_job(job_id)
        with lock:
            with get_db_session() as session:
                next_seq = self._next_seq(session, job_id)

                # Persist streaming deltas into job_cards.output so snapshots can show partial results.
                if event_type == "card.delta" and card_id is not None:
                    self._apply_card_delta(session, card_id=int(card_id), payload=payload)
                if event_type == "card.append" and card_id is not None:
                    self._apply_card_append(session, card_id=int(card_id), payload=payload)

                event = AnalysisJobEvent(
                    job_id=job_id,
                    card_id=card_id,
                    seq=next_seq,
                    event_type=str(event_type),
                    payload=payload,
                )
                session.add(event)
                # Best-effort same-process SSE push: publish without waiting for DB polling.
                self._publish_to_bus_best_effort(
                    job_id=str(job_id),
                    seq=int(next_seq or 0),
                    event_type=str(event_type),
                    payload=dict(payload or {}),
                )
                # Avoid session.refresh(): it costs an extra DB round-trip and callers don't need it.
                return event

    def fetch_events(self, job_id: str, *, after_seq: int, limit: int) -> list[AnalysisJobEvent]:
        with get_db_session() as session:
            rows = (
                session.query(AnalysisJobEvent)
                .filter(AnalysisJobEvent.job_id == job_id, AnalysisJobEvent.seq > int(after_seq or 0))
                .order_by(AnalysisJobEvent.seq.asc())
                .limit(int(limit or _SSE_BATCH_SIZE))
                .all()
            )
        return list(rows or [])

    def get_last_seq(self, job_id: str) -> int:
        with get_db_session() as session:
            job = session.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job is not None:
                try:
                    last = int(getattr(job, "last_seq", 0) or 0)
                except Exception:  # noqa: BLE001
                    last = 0
                if last > 0:
                    return last
            max_seq = (
                session.query(func.max(AnalysisJobEvent.seq))
                .filter(AnalysisJobEvent.job_id == job_id)
                .scalar()
            )
            return int(max_seq or 0)

    def get_card_output(self, *, card_id: int) -> Dict[str, Any]:
        with get_db_session() as session:
            row = session.query(AnalysisJobCard.output).filter(AnalysisJobCard.id == int(card_id)).first()
            payload = row[0] if row else None
        return ensure_output_envelope(payload)

    def get_card_outputs(self, *, card_ids: list[int]) -> Dict[int, Dict[str, Any]]:
        if not card_ids:
            return {}
        out: Dict[int, Dict[str, Any]] = {}
        with get_db_session() as session:
            rows = (
                session.query(AnalysisJobCard.id, AnalysisJobCard.output)
                .filter(AnalysisJobCard.id.in_([int(cid) for cid in card_ids if cid]))
                .all()
            )
        for cid, payload in rows:
            try:
                out[int(cid)] = ensure_output_envelope(payload)
            except Exception:
                continue
        return out

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
        terminal_event_types = {"job.completed"}
        terminal_seq: Optional[int] = None
        saw_terminal_event = False
        use_bus = self._use_event_bus_for_stream()
        bus_sub = None
        if use_bus:
            try:
                bus_sub = get_event_bus().subscribe(job_id=str(job_id))
            except Exception:
                bus_sub = None
                use_bus = False

        def _refresh_terminal_seq() -> None:
            nonlocal terminal_seq
            if terminal_seq is not None or job_store is None:
                return
            try:
                job = job_store.get_job(job_id)
            except Exception:
                job = None
            if job is None:
                terminal_seq = last_seq
                return
            if str(getattr(job, "status", "") or "") in terminal_states:
                # Best-effort: locate the terminal event seq in DB.
                try:
                    with get_db_session() as session:
                        max_seq = (
                            session.query(func.max(AnalysisJobEvent.seq))
                            .filter(
                                AnalysisJobEvent.job_id == job_id,
                                AnalysisJobEvent.event_type.in_(tuple(terminal_event_types)),
                            )
                            .scalar()
                        )
                    terminal_seq = int(max_seq) if max_seq is not None else (int(last_seq) + 1)
                except Exception:
                    terminal_seq = int(last_seq) + 1

        try:
            # Bootstrap: emit any buffered events already persisted in DB.
            while True:
                events = self.fetch_events(job_id, after_seq=last_seq, limit=_SSE_BATCH_SIZE)
                if not events:
                    break
                for ev in events:
                    last_seq = int(ev.seq or last_seq)
                    payload = ev.payload or {}
                    payload.setdefault("job_id", job_id)
                    payload.setdefault("seq", last_seq)
                    yield format_stream_message(
                        create_event(
                            source="analysis",
                            event_type=str(ev.event_type),
                            message="",
                            payload=payload,
                        )
                    )
                    last_activity = time.monotonic()
                    if str(ev.event_type) in terminal_event_types:
                        terminal_seq = int(ev.seq or terminal_seq or last_seq)
                        saw_terminal_event = True
                if len(events) < _SSE_BATCH_SIZE:
                    break

            while True:
                # Stop once we've reached the terminal seq and waited the grace period.
                if stop_when_done:
                    _refresh_terminal_seq()
                    if terminal_seq is not None and last_seq >= terminal_seq:
                        if (time.monotonic() - last_activity) >= float(terminal_grace_seconds or 0):
                            break

                next_bus_ev = None
                if use_bus and bus_sub is not None:
                    now = time.monotonic()
                    time_to_keepalive = max(0.0, float(keepalive_seconds) - (now - last_activity)) if keepalive_seconds else None
                    time_to_terminal = (
                        max(0.0, float(terminal_grace_seconds or 0) - (now - last_activity))
                        if stop_when_done and terminal_seq is not None and last_seq >= terminal_seq
                        else None
                    )

                    # Always wake up frequently enough to provide a DB-poll fallback even if backplane
                    # messages are missed/dropped. Keepalive/terminal timers can shorten the wait further.
                    timeout_s = float(poll_interval) if poll_interval else 0.5
                    if time_to_keepalive is not None:
                        timeout_s = min(timeout_s, time_to_keepalive)
                    if time_to_terminal is not None:
                        timeout_s = min(timeout_s, time_to_terminal)
                    timeout_s = max(0.05, float(timeout_s))
                    next_bus_ev = bus_sub.get(timeout_s=timeout_s)

                if next_bus_ev is not None:
                    # Ignore duplicates/out-of-order (resume catch-up comes from DB bootstrap).
                    if int(next_bus_ev.seq or 0) <= int(last_seq or 0):
                        continue
                    # Wakeup-only events (from cross-process backplanes) trigger a DB fetch.
                    if str(getattr(next_bus_ev, "event_type", "") or "") == "wakeup" or not str(getattr(next_bus_ev, "message", "") or ""):
                        events = self.fetch_events(job_id, after_seq=last_seq, limit=_SSE_BATCH_SIZE)
                        if events:
                            for ev in events:
                                last_seq = int(ev.seq or last_seq)
                                payload = ev.payload or {}
                                payload.setdefault("job_id", job_id)
                                payload.setdefault("seq", last_seq)
                                yield format_stream_message(create_event(source="analysis", event_type=str(ev.event_type), message="", payload=payload))
                                last_activity = time.monotonic()
                                if str(ev.event_type) in terminal_event_types:
                                    terminal_seq = int(ev.seq or terminal_seq or last_seq)
                                    saw_terminal_event = True
                        continue
                    # Gap safety: if we somehow missed an event, backfill from DB.
                    if int(next_bus_ev.seq) > int(last_seq) + 1:
                        missing = self.fetch_events(job_id, after_seq=last_seq, limit=_SSE_BATCH_SIZE)
                        if missing:
                            for ev in missing:
                                last_seq = int(ev.seq or last_seq)
                                payload = ev.payload or {}
                                payload.setdefault("job_id", job_id)
                                payload.setdefault("seq", last_seq)
                                yield format_stream_message(create_event(source="analysis", event_type=str(ev.event_type), message="", payload=payload))
                                last_activity = time.monotonic()
                                if str(ev.event_type) in terminal_event_types:
                                    terminal_seq = int(ev.seq or terminal_seq or last_seq)
                                    saw_terminal_event = True
                            continue
                    yield str(next_bus_ev.message)
                    last_seq = int(next_bus_ev.seq)
                    last_activity = time.monotonic()
                    if str(next_bus_ev.event_type) in terminal_event_types:
                        terminal_seq = int(next_bus_ev.seq or terminal_seq or last_seq)
                        saw_terminal_event = True
                    continue

                # No bus event: best-effort DB poll fallback (protects against missed backplane messages).
                events = self.fetch_events(job_id, after_seq=last_seq, limit=_SSE_BATCH_SIZE)
                if events:
                    for ev in events:
                        last_seq = int(ev.seq or last_seq)
                        payload = ev.payload or {}
                        payload.setdefault("job_id", job_id)
                        payload.setdefault("seq", last_seq)
                        yield format_stream_message(create_event(source="analysis", event_type=str(ev.event_type), message="", payload=payload))
                        last_activity = time.monotonic()
                        if str(ev.event_type) in terminal_event_types:
                            terminal_seq = int(ev.seq or terminal_seq or last_seq)
                            saw_terminal_event = True
                    continue
                # When bus is disabled, keep the original cadence.
                if not use_bus:
                    time.sleep(float(poll_interval))

                if stop_when_done:
                    _refresh_terminal_seq()
                    # If the job is terminal but we didn't see a terminal event, synthesize one.
                    if terminal_seq is not None and not saw_terminal_event and last_seq < terminal_seq and job_store is not None:
                        try:
                            job = job_store.get_job(job_id)
                        except Exception:
                            job = None
                        status = str(getattr(job, "status", "") or "").strip().lower() if job is not None else ""
                        if status in terminal_states:
                            payload = {"job_id": job_id, "seq": int(terminal_seq), "status": status}
                            yield format_stream_message(create_event(source="analysis", event_type="job.completed", message="", payload=payload))
                            last_seq = int(terminal_seq)
                            break

                if keepalive_seconds and (time.monotonic() - last_activity) >= float(keepalive_seconds):
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
        finally:
            try:
                if bus_sub is not None:
                    bus_sub.close()
            except Exception:
                pass

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

        raw_path = str(payload.get("path") or "items").strip()
        path = [p for p in raw_path.split(".") if p]
        if not path:
            path = ["items"]

        dedup_key = payload.get("dedup_key")
        dedup_key = str(dedup_key).strip() if dedup_key is not None else ""
        cursor = payload.get("cursor")
        partial = bool(payload.get("partial"))

        q = session.query(AnalysisJobCard).filter(AnalysisJobCard.id == int(card_id))
        try:
            q = q.with_for_update()
        except Exception:  # noqa: BLE001
            pass
        card = q.first()
        if card is None:
            return

        env = ensure_output_envelope(getattr(card, "output", None))
        data = env.get("data")
        if not isinstance(data, dict):
            data = {}
        root: Dict[str, Any] = dict(data)

        # Navigate to parent dict.
        parent: Dict[str, Any] = root
        for key in path[:-1]:
            cur = parent.get(key)
            if not isinstance(cur, dict):
                cur = {}
            cur2 = dict(cur)
            parent[key] = cur2
            parent = cur2

        leaf = path[-1]
        existing = parent.get(leaf)
        existing_list = existing if isinstance(existing, list) else []
        merged_list: list[Any] = list(existing_list)

        if dedup_key:
            seen: set[str] = set()
            for it in merged_list:
                if isinstance(it, dict) and it.get(dedup_key) is not None:
                    seen.add(str(it.get(dedup_key)))
            for it in items:
                if isinstance(it, dict) and it.get(dedup_key) is not None:
                    k = str(it.get(dedup_key))
                    if k in seen:
                        continue
                    seen.add(k)
                merged_list.append(it)
        else:
            merged_list.extend(items)

        parent[leaf] = merged_list
        if cursor is not None:
            root["cursor"] = cursor
        if partial:
            root["partial"] = True

        stream = env.get("stream")
        if not isinstance(stream, dict):
            stream = {}

        card.output = {"data": root, "stream": stream}
        try:
            card.updated_at = datetime.utcnow()
        except Exception:
            pass
