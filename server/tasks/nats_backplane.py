"""
Optional NATS backplane for multi-process SSE push.

Design goals:
- Postgres remains the source of truth (job_events for replay/resume).
- NATS is a best-effort low-latency wakeup/data plane between processes.
- If NATS is down or messages are dropped, SSE falls back to DB polling.

Env:
  DINQ_ANALYZE_SSE_BACKPLANE=none|nats
  DINQ_NATS_URL=nats://127.0.0.1:4222
  DINQ_NATS_SUBJECT=dinq.job_events
  DINQ_NATS_PUBLISH_MODE=auto|full|wakeup
  DINQ_NATS_MAX_EVENT_BYTES=65536   (used when publish_mode=auto)
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict
from typing import Optional

from server.tasks.event_bus import BusEvent, get_event_bus


logger = logging.getLogger(__name__)


def _env(name: str, default: str) -> str:
    return str(os.getenv(name) or default).strip()


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def backplane_mode() -> str:
    return _env("DINQ_ANALYZE_SSE_BACKPLANE", "none").lower()


class NatsBackplane:
    def __init__(self) -> None:
        self._url = _env("DINQ_NATS_URL", "nats://127.0.0.1:4222")
        self._subject = _env("DINQ_NATS_SUBJECT", "dinq.job_events")
        self._publish_mode = _env("DINQ_NATS_PUBLISH_MODE", "auto").lower()
        self._max_event_bytes = max(1024, min(_int_env("DINQ_NATS_MAX_EVENT_BYTES", 65536), 8 * 1024 * 1024))

        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._loop = None
        self._queue = None
        self._started = threading.Event()

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run, daemon=True, name="dinq-nats-backplane")
            self._thread.start()
        # Best-effort: do not block startup.
        self._started.wait(timeout=1.0)

    def publish(self, ev: BusEvent) -> None:
        """
        Best-effort publish.

        Depending on DINQ_NATS_PUBLISH_MODE:
          - wakeup: only publish {job_id, seq, event_type="wakeup"}
          - full: publish full BusEvent (including SSE message)
          - auto: full when <= max bytes; else wakeup
        """

        loop = self._loop
        q = self._queue
        if loop is None or q is None:
            # Lazy start.
            self.start()
            loop = self._loop
            q = self._queue
            if loop is None or q is None:
                return

        payload: dict
        mode = str(self._publish_mode or "auto").lower()
        if mode in ("wakeup", "signal"):
            payload = {"job_id": ev.job_id, "seq": int(ev.seq or 0), "event_type": "wakeup"}
        elif mode in ("full", "event"):
            payload = asdict(ev)
        else:
            # auto
            raw = json.dumps(asdict(ev), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(raw) <= int(self._max_event_bytes):
                payload = json.loads(raw.decode("utf-8"))
            else:
                payload = {"job_id": ev.job_id, "seq": int(ev.seq or 0), "event_type": "wakeup"}

        try:
            loop.call_soon_threadsafe(q.put_nowait, payload)
        except Exception:
            return

    def _run(self) -> None:
        try:
            import asyncio
            from nats.aio.client import Client as NATS  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            logger.warning("NATS backplane disabled (missing dependency): %s", exc)
            return

        import asyncio

        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        import asyncio

        try:
            from nats.aio.client import Client as NATS
        except Exception as exc:  # pragma: no cover
            logger.warning("NATS backplane disabled (missing dependency): %s", exc)
            return

        loop = asyncio.get_running_loop()
        q: "asyncio.Queue[dict]" = asyncio.Queue(maxsize=20000)
        self._loop = loop
        self._queue = q

        nc = NATS()
        try:
            await nc.connect(
                servers=[self._url],
                name="dinq",
                no_echo=True,
                reconnect_time_wait=0.5,
                max_reconnect_attempts=-1,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("NATS connect failed (%s): %s", self._url, exc)
            return

        self._started.set()

        async def _on_msg(msg) -> None:  # type: ignore[no-untyped-def]
            try:
                raw = bytes(msg.data or b"").decode("utf-8", errors="replace")
                data = json.loads(raw) if raw else {}
            except Exception:
                return

            if not isinstance(data, dict):
                return
            job_id = str(data.get("job_id") or "").strip()
            if not job_id:
                return
            try:
                seq = int(data.get("seq") or 0)
            except Exception:
                seq = 0
            event_type = str(data.get("event_type") or "wakeup")
            message = str(data.get("message") or "")

            try:
                get_event_bus().publish(
                    BusEvent(
                        job_id=job_id,
                        seq=seq,
                        event_type=event_type,
                        message=message,
                    )
                )
            except Exception:
                return

        try:
            await nc.subscribe(self._subject, cb=_on_msg)
        except Exception as exc:  # noqa: BLE001
            logger.warning("NATS subscribe failed (%s): %s", self._subject, exc)
            try:
                await nc.close()
            except Exception:
                pass
            return

        async def _publisher_loop() -> None:
            while True:
                item = await q.get()
                try:
                    raw = json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    await nc.publish(self._subject, raw)
                except Exception:
                    # Best-effort: drop on failures.
                    pass

        # Run publisher forever (subscriber callbacks are handled by NATS).
        await _publisher_loop()


_BP: Optional[NatsBackplane] = None
_BP_LOCK = threading.Lock()


def get_nats_backplane() -> Optional[NatsBackplane]:
    if backplane_mode() != "nats":
        return None
    global _BP
    with _BP_LOCK:
        if _BP is None:
            _BP = NatsBackplane()
            _BP.start()
        return _BP

