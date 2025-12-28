import threading
import unittest

from server.services.scholar.cancel import ScholarTaskCancelled, raise_if_cancelled
from server.utils.streaming_task_builder import StreamingTaskContext


class TestStreamingTaskContextEmitRaw(unittest.TestCase):
    def test_emit_raw_sets_source_when_missing(self) -> None:
        events = []

        def progress_cb(event):
            events.append(event)

        ctx = StreamingTaskContext(source="scholar", progress_cb=progress_cb, cancel_event=None)
        ctx.emit_raw({"event_type": "progress", "message": "hi"})

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].get("source"), "scholar")

    def test_emit_raw_respects_cancellation(self) -> None:
        events = []
        cancel_event = threading.Event()
        cancel_event.set()

        def progress_cb(event):
            events.append(event)

        ctx = StreamingTaskContext(source="scholar", progress_cb=progress_cb, cancel_event=cancel_event)
        ctx.emit_raw({"event_type": "progress", "message": "hi"})

        self.assertEqual(events, [])


class TestScholarCancelHelpers(unittest.TestCase):
    def test_raise_if_cancelled_raises(self) -> None:
        cancel_event = threading.Event()
        cancel_event.set()
        with self.assertRaises(ScholarTaskCancelled):
            raise_if_cancelled(cancel_event)

