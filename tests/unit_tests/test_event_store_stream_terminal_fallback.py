import json
import unittest

from src.models.db import AnalysisJobEvent


class _FakeJob:
    def __init__(self, status: str):
        self.status = status


class _FakeJobStore:
    def __init__(self, status: str):
        self._status = status

    def get_job(self, job_id):  # noqa: ARG002
        return _FakeJob(self._status)


class TestEventStoreStreamTerminalFallback(unittest.TestCase):
    def test_stream_events_yields_terminal_event_and_stops(self):
        from server.tasks.event_store import EventStore

        store = EventStore()

        calls = {"n": 0}

        def _fake_fetch_events(job_id, *, after_seq, limit=500):  # noqa: ARG001
            calls["n"] += 1
            if calls["n"] == 1:
                return [
                    AnalysisJobEvent(
                        job_id=job_id,
                        card_id=None,
                        seq=5,
                        event_type="job.completed",
                        payload={"status": "completed"},
                    )
                ]
            return []

        store.fetch_events = _fake_fetch_events  # type: ignore[method-assign]

        gen = store.stream_events(
            job_id="job123",
            after_seq=0,
            stop_when_done=True,
            job_store=_FakeJobStore(status="completed"),
            keepalive_seconds=0,
            poll_interval=0,
            terminal_grace_seconds=0,
        )

        msg = next(gen)
        raw = msg.strip()
        self.assertTrue(raw.startswith("data: "))
        evt = json.loads(raw[len("data: ") :])
        self.assertEqual(evt.get("event_type"), "job.completed")
        payload = evt.get("payload") or {}
        self.assertEqual(payload.get("status"), "completed")

        with self.assertRaises(StopIteration):
            next(gen)


if __name__ == "__main__":
    unittest.main()
