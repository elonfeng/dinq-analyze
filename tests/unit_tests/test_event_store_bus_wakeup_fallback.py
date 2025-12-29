import json
import unittest
from unittest.mock import patch

from src.models.db import AnalysisJobEvent


class _FakeBusSub:
    def __init__(self, ev):
        self._ev = ev
        self._used = False

    def get(self, *, timeout_s=None):  # noqa: ARG002
        if self._used:
            return None
        self._used = True
        return self._ev

    def close(self):
        return None


class _FakeBus:
    def __init__(self, ev):
        self._ev = ev

    def subscribe(self, *, job_id):  # noqa: ARG002
        return _FakeBusSub(self._ev)


class TestEventStoreBusWakeupFallback(unittest.TestCase):
    def test_stream_events_wakeup_triggers_db_fetch(self):
        from server.tasks.event_bus import BusEvent
        from server.tasks.event_store import EventStore

        store = EventStore()
        store._use_event_bus_for_stream = lambda: True  # type: ignore[method-assign]

        calls = {"n": 0}

        def _fake_fetch_events(job_id, *, after_seq, limit=500):  # noqa: ARG001
            calls["n"] += 1
            if calls["n"] == 1:
                # bootstrap: no persisted events yet
                return []
            return [
                AnalysisJobEvent(
                    job_id=job_id,
                    card_id=None,
                    seq=2,
                    event_type="card.progress",
                    payload={"job_id": job_id, "seq": 2, "card": "profile", "step": "x"},
                )
            ]

        store.fetch_events = _fake_fetch_events  # type: ignore[method-assign]

        wake = BusEvent(job_id="job123", seq=2, event_type="wakeup", message="")
        fake_bus = _FakeBus(wake)

        with patch("server.tasks.event_store.get_event_bus", lambda: fake_bus):
            gen = store.stream_events(
                job_id="job123",
                after_seq=0,
                keepalive_seconds=0,
                poll_interval=0.01,
                stop_when_done=False,
            )
            msg = next(gen)

        raw = msg.strip()
        self.assertTrue(raw.startswith("data: "))
        evt = json.loads(raw[len("data: ") :])
        self.assertEqual(evt.get("event_type"), "card.progress")
        payload = evt.get("payload") or {}
        self.assertEqual(payload.get("seq"), 2)


if __name__ == "__main__":
    unittest.main()

