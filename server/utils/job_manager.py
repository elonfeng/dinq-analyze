"""
Job Manager (in-process)

提供一个轻量的后台任务队列 + 事件流（SSE）订阅能力，用于：
- 先快速返回结果（例如简化报告）
- 后台补齐（enrich/full refresh）
- 前端用 job_id 订阅补齐进度与完成事件

说明：
- 这是“单进程”实现：进程重启后 job 会丢失；适用于本地/单实例部署。
- 需要跨进程全局队列/限流时，可后续替换为 Redis/Celery 等。
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

from server.utils.stream_protocol import create_event, format_stream_message


def _now_seconds() -> float:
    return time.time()


@dataclass
class JobRecord:
    job_id: str
    kind: str
    user_id: str
    created_at: float = field(default_factory=_now_seconds)
    status: str = "queued"  # queued|running|succeeded|failed|canceled
    cancel_event: threading.Event = field(default_factory=threading.Event)
    last_seq: int = 0
    events: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    done_at: Optional[float] = None
    cond: threading.Condition = field(default_factory=lambda: threading.Condition(threading.Lock()))


class JobContext:
    def __init__(self, *, manager: "JobManager", record: JobRecord):
        self._manager = manager
        self.record = record

    @property
    def job_id(self) -> str:
        return self.record.job_id

    @property
    def user_id(self) -> str:
        return self.record.user_id

    @property
    def cancel_event(self) -> threading.Event:
        return self.record.cancel_event

    def cancelled(self) -> bool:
        return bool(self.cancel_event.is_set())

    def emit(self, event: Dict[str, Any]) -> None:
        self._manager.emit(self.job_id, event)

    def progress(self, *, message: str, step: str, progress: Optional[float] = None, payload: Optional[Dict[str, Any]] = None) -> None:
        self.emit(
            create_event(
                source="scholar_enrich",
                event_type="progress",
                message=message,
                step=step,
                progress=progress,
                payload=payload,
            )
        )

    def data(self, *, message: str, step: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self.emit(
            create_event(
                source="scholar_enrich",
                event_type="data",
                message=message,
                step=step,
                payload=payload,
            )
        )


class JobManager:
    def __init__(self, *, max_events_per_job: int = 500, max_workers: int = 4):
        self._max_events = max(50, int(max_events_per_job))
        self._jobs: Dict[str, JobRecord] = {}
        self._job_keys: Dict[str, str] = {}  # job_key -> job_id
        self._lock = threading.Lock()
        self._executor = threading.Thread  # placeholder type
        self._work_q: "queue.Queue[tuple[str, Any]]" = queue.Queue()
        self._workers: List[threading.Thread] = []
        self._max_workers = max(1, int(max_workers))
        self._start_workers()

    def _start_workers(self) -> None:
        for i in range(self._max_workers):
            t = threading.Thread(target=self._worker_loop, name=f"dinq-job-worker-{i}", daemon=True)
            t.start()
            self._workers.append(t)

    def _worker_loop(self) -> None:
        while True:
            job_id, fn = self._work_q.get()
            record = self.get(job_id)
            if record is None:
                continue

            with record.cond:
                if record.status in ("canceled", "succeeded", "failed"):
                    continue
                record.status = "running"
                record.cond.notify_all()

            try:
                ctx = JobContext(manager=self, record=record)
                self.emit(
                    job_id,
                    create_event(
                        source="scholar_enrich",
                        event_type="start",
                        message="Job started",
                        step="start",
                        payload={"job_id": job_id, "kind": record.kind},
                    ),
                )
                result = fn(ctx)
                if record.cancel_event.is_set():
                    raise RuntimeError("canceled")

                with record.cond:
                    record.status = "succeeded"
                    record.result = result if isinstance(result, dict) else {"result": result}
                    record.done_at = _now_seconds()
                    record.cond.notify_all()

                self.emit(
                    job_id,
                    create_event(
                        source="scholar_enrich",
                        event_type="final",
                        message="Job completed",
                        step="final",
                        payload=record.result,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                code = "cancelled" if str(exc).lower().startswith("canceled") or record.cancel_event.is_set() else "internal_error"
                err = {
                    "code": code,
                    "message": str(exc),
                    "retryable": code in ("cancelled",),
                    "detail": {"job_id": job_id, "kind": record.kind},
                }
                with record.cond:
                    record.status = "canceled" if code == "cancelled" else "failed"
                    record.error = err
                    record.done_at = _now_seconds()
                    record.cond.notify_all()

                self.emit(
                    job_id,
                    create_event(
                        source="scholar_enrich",
                        event_type="error",
                        message=err["message"],
                        step="error",
                        payload=err,
                    ),
                )
            finally:
                self.emit(
                    job_id,
                    create_event(
                        source="scholar_enrich",
                        event_type="end",
                        message="Job stream closed",
                        step="end",
                        payload={"job_id": job_id},
                    ),
                )

    def create(self, *, kind: str, user_id: str) -> str:
        job_id = uuid.uuid4().hex
        rec = JobRecord(job_id=job_id, kind=str(kind), user_id=str(user_id))
        with self._lock:
            self._jobs[job_id] = rec
        return job_id

    def create_or_get(self, *, job_key: str, kind: str, user_id: str) -> str:
        """
        Idempotent job creation (per-process).

        job_key 需要包含 user_id 维度（否则会因为鉴权导致其它用户拿不到同一个 job）。
        """

        key = str(job_key)
        with self._lock:
            existing_id = self._job_keys.get(key)
            if existing_id:
                rec = self._jobs.get(existing_id)
                if rec and rec.status not in ("succeeded", "failed", "canceled"):
                    return existing_id
                # stale mapping: drop and recreate
                self._job_keys.pop(key, None)

            job_id = uuid.uuid4().hex
            rec = JobRecord(job_id=job_id, kind=str(kind), user_id=str(user_id))
            self._jobs[job_id] = rec
            self._job_keys[key] = job_id
            return job_id

    def submit(self, job_id: str, fn) -> None:  # type: ignore[no-untyped-def]
        self._work_q.put((job_id, fn))

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        rec = self.get(job_id)
        if rec is None:
            return False
        rec.cancel_event.set()
        with rec.cond:
            if rec.status not in ("succeeded", "failed", "canceled"):
                rec.status = "canceled"
                rec.done_at = _now_seconds()
                rec.cond.notify_all()
        return True

    def emit(self, job_id: str, event: Dict[str, Any]) -> None:
        rec = self.get(job_id)
        if rec is None:
            return

        with rec.cond:
            rec.last_seq += 1
            event = dict(event or {})
            event.setdefault("payload", {})
            if isinstance(event.get("payload"), dict):
                event["payload"].setdefault("job_id", job_id)
                event["payload"].setdefault("seq", rec.last_seq)
            else:
                event["payload"] = {"job_id": job_id, "seq": rec.last_seq}

            rec.events.append(event)
            if len(rec.events) > self._max_events:
                rec.events = rec.events[-self._max_events :]

            rec.cond.notify_all()

    def stream_sse(
        self,
        *,
        job_id: str,
        after_seq: int = 0,
        keepalive_seconds: float = 15.0,
    ) -> Generator[str, None, None]:
        rec = self.get(job_id)
        if rec is None:
            yield format_stream_message(
                create_event(
                    source="scholar_enrich",
                    event_type="error",
                    message="job not found",
                    step="not_found",
                    payload={"code": "not_found", "message": "job not found", "retryable": False, "detail": {"job_id": job_id}},
                )
            )
            yield format_stream_message(create_event(source="scholar_enrich", event_type="end", message="job stream closed"))
            return

        last_sent = int(after_seq or 0)
        last_activity = time.monotonic()

        while True:
            with rec.cond:
                # Emit backlog first
                backlog = [e for e in rec.events if int(e.get("payload", {}).get("seq", 0) or 0) > last_sent]
                if not backlog:
                    rec.cond.wait(timeout=0.5)
                    backlog = [e for e in rec.events if int(e.get("payload", {}).get("seq", 0) or 0) > last_sent]

            for e in backlog:
                seq = int(e.get("payload", {}).get("seq", 0) or 0)
                if seq <= last_sent:
                    continue
                yield format_stream_message(e)
                last_sent = seq
                last_activity = time.monotonic()

            # keepalive
            now = time.monotonic()
            if keepalive_seconds and now - last_activity >= keepalive_seconds:
                ping = create_event(
                    source="scholar_enrich",
                    event_type="ping",
                    message="",
                    step="keepalive",
                    legacy_type="ping",
                )
                ping.setdefault("content", "")
                yield format_stream_message(ping)
                last_activity = now

            # done?
            rec2 = self.get(job_id)
            if rec2 is None:
                return
            if rec2.status in ("succeeded", "failed", "canceled") and rec2.done_at is not None:
                # Ensure end event is eventually emitted by worker; but if client connects late, emit one.
                if last_sent >= rec2.last_seq:
                    return
