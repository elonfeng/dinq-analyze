"""
In-memory event bus for low-latency SSE streaming (same-process).

This bus is intentionally best-effort and process-local:
- Great for local/in-process execution where the scheduler and SSE live together.
- Not suitable as the only transport in multi-process / multi-instance deployments.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class BusEvent:
    job_id: str
    seq: int
    event_type: str
    message: str


class EventSubscription:
    def __init__(self, *, bus: "InMemoryEventBus", job_id: str) -> None:
        self._bus = bus
        self.job_id = str(job_id)
        self._queue: "queue.Queue[BusEvent]" = queue.Queue()
        self._closed = threading.Event()

    def get(self, *, timeout_s: Optional[float] = None) -> Optional[BusEvent]:
        if self._closed.is_set():
            return None
        try:
            return self._queue.get(timeout=timeout_s)
        except queue.Empty:
            return None

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        self._bus.unsubscribe(self)

    def __enter__(self) -> "EventSubscription":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.close()

    def _put(self, ev: BusEvent) -> None:
        if self._closed.is_set():
            return
        # Unbounded queue: best-effort and avoids blocking analysis execution.
        self._queue.put_nowait(ev)


class InMemoryEventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: Dict[str, Dict[int, EventSubscription]] = {}
        self._next_id = 0

    def subscribe(self, *, job_id: str) -> EventSubscription:
        sub = EventSubscription(bus=self, job_id=str(job_id))
        with self._lock:
            self._next_id += 1
            sid = int(self._next_id)
            self._subs.setdefault(str(job_id), {})[sid] = sub
        return sub

    def unsubscribe(self, sub: EventSubscription) -> None:
        job_id = str(getattr(sub, "job_id", "") or "")
        if not job_id:
            return
        with self._lock:
            by_id = self._subs.get(job_id)
            if not by_id:
                return
            to_delete = None
            for sid, cur in by_id.items():
                if cur is sub:
                    to_delete = sid
                    break
            if to_delete is not None:
                by_id.pop(int(to_delete), None)
            if not by_id:
                self._subs.pop(job_id, None)

    def publish(self, ev: BusEvent) -> None:
        job_id = str(ev.job_id or "")
        if not job_id:
            return
        with self._lock:
            by_id = dict(self._subs.get(job_id) or {})
        for sub in by_id.values():
            try:
                sub._put(ev)
            except Exception:
                continue


_BUS: Optional[InMemoryEventBus] = None
_BUS_LOCK = threading.Lock()


def get_event_bus() -> InMemoryEventBus:
    global _BUS
    with _BUS_LOCK:
        if _BUS is None:
            _BUS = InMemoryEventBus()
        return _BUS

