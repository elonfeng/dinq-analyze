import json
import time
import unittest
import threading

from server.utils.stream_task import run_streaming_task


def _parse_sse_data(line: str) -> dict:
    if not line.startswith("data: "):
        raise AssertionError(f"not an SSE data line: {line!r}")
    raw = line[len("data: ") :].strip()
    return json.loads(raw)


class TestRunStreamingTask(unittest.TestCase):
    def test_emits_progress_final_end(self):
        def task_fn(progress_cb, result_queue):
            progress_cb({"event_type": "progress", "message": "step1"})
            result_queue.put(("success", {"ok": True}))

        chunks = list(
            run_streaming_task(
                source="test",
                task_fn=task_fn,
                timeout_seconds=5,
            )
        )

        self.assertGreaterEqual(len(chunks), 2)
        first = _parse_sse_data(chunks[0])
        self.assertEqual(first["source"], "test")
        self.assertEqual(first["event_type"], "progress")

        last = _parse_sse_data(chunks[-1])
        self.assertEqual(last["event_type"], "end")

    def test_allows_raw_sse_strings(self):
        raw = "data: {\"hello\": \"world\"}\n\n"

        def task_fn(progress_cb, result_queue):
            progress_cb(raw)
            result_queue.put(("success", {"ok": True}))

        chunks = list(
            run_streaming_task(
                source="test",
                task_fn=task_fn,
                timeout_seconds=5,
            )
        )

        self.assertIn(raw, chunks)

    def test_timeout_emits_error_and_end(self):
        def task_fn(progress_cb, result_queue):
            time.sleep(2)

        chunks = list(
            run_streaming_task(
                source="test",
                task_fn=task_fn,
                timeout_seconds=0.01,
            )
        )

        parsed = [_parse_sse_data(c) for c in chunks if c.startswith("data: ")]
        self.assertTrue(any(e.get("event_type") == "error" for e in parsed))
        self.assertEqual(parsed[-1].get("event_type"), "end")

    def test_passes_cancel_event_when_supported(self):
        seen = []

        def task_fn(progress_cb, result_queue, cancel_event):
            seen.append(cancel_event)
            progress_cb({"event_type": "progress", "message": "hello"})
            result_queue.put(("success", {"ok": True}))

        list(
            run_streaming_task(
                source="test",
                task_fn=task_fn,
                timeout_seconds=5,
            )
        )

        self.assertEqual(len(seen), 1)
        self.assertTrue(hasattr(seen[0], "is_set"))

    def test_timeout_sets_cancel_event_for_cooperative_task(self):
        done = threading.Event()

        def task_fn(progress_cb, result_queue, cancel_event):
            while not cancel_event.is_set():
                time.sleep(0.01)
            done.set()

        list(
            run_streaming_task(
                source="test",
                task_fn=task_fn,
                timeout_seconds=0.02,
            )
        )

        self.assertTrue(done.wait(timeout=1.0))


if __name__ == "__main__":
    unittest.main()
