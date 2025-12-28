import json
import unittest
from unittest.mock import patch

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
    def test_stream_events_recovers_terminal_event_from_db(self):
        with patch("server.tasks.event_store.get_redis_client", return_value=None):
            from server.tasks.event_store import EventStore

            store = EventStore()

        # Simulate: realtime stream has no more events, but DB says the job is terminal and has a terminal event.
        store.fetch_events = lambda job_id, after_seq, limit=500: []  # noqa: E731
        store._get_terminal_seq = lambda job_id, terminal_event_types: 5  # noqa: E731
        store._fetch_events_db = (  # noqa: E731
            lambda job_id, after_seq, limit=500: [
                AnalysisJobEvent(
                    job_id=job_id,
                    card_id=None,
                    seq=5,
                    event_type="job.completed",
                    payload={"status": "completed"},
                )
            ]
        )

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

