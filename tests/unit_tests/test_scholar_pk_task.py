import queue
import sys
import threading
import types
import unittest
from unittest.mock import patch


class TestScholarPKTask(unittest.TestCase):
    def test_pk_runs_two_scholar_analyses_in_parallel(self):
        from server.api.scholar_pk.pk_processor import build_scholar_pk_task_fn

        active_sessions = {}
        task_fn = build_scholar_pk_task_fn(
            query1="id1AAAAJ",
            query2="id2AAAAJ",
            active_sessions=active_sessions,
            user_id="u1",
            trace_id="t1",
        )

        events = []

        def progress_cb(event):
            events.append(event)

        result_queue = queue.Queue(maxsize=1)
        cancel_event = threading.Event()

        started = {1: threading.Event(), 2: threading.Event()}

        def fake_run_scholar_analysis(
            *,
            researcher_name=None,
            scholar_id=None,
            callback=None,
            cancel_event=None,
            user_id=None,
            **_kwargs,
        ):
            self.assertIsNotNone(cancel_event)
            self.assertEqual(user_id, "u1")
            idx = 1 if scholar_id == "id1AAAAJ" else 2
            started[idx].set()

            other = started[2 if idx == 1 else 1]
            if not other.wait(timeout=0.5):
                raise AssertionError("Expected two researchers to run concurrently")

            if callback is not None:
                callback({"message": "half", "progress": 50})

            return {
                "researcher": {"name": f"R{idx}", "scholar_id": scholar_id},
                "publication_stats": {},
            }

        dummy_scholar_service = types.ModuleType("server.services.scholar.scholar_service")
        dummy_scholar_service.run_scholar_analysis = fake_run_scholar_analysis

        original = sys.modules.get("server.services.scholar.scholar_service")
        sys.modules["server.services.scholar.scholar_service"] = dummy_scholar_service
        try:
            with patch("server.api.scholar_pk.pk_processor.get_scholar_from_cache", return_value=None), patch(
                "server.api.scholar_pk.pk_processor.process_pk_data",
                return_value={"researcher1": {}, "researcher2": {}, "roast": "ok"},
            ), patch(
                "server.api.scholar_pk.pk_processor.save_pk_report",
                return_value={
                    "pk_json_url": "http://example.com/pk.json",
                    "researcher1_name": "A",
                    "researcher2_name": "B",
                },
            ), patch(
                "server.api.scholar_pk.pk_processor.track_stream_completion",
                return_value=None,
            ):
                task_fn(progress_cb, result_queue, cancel_event)
        finally:
            if original is None:
                sys.modules.pop("server.services.scholar.scholar_service", None)
            else:
                sys.modules["server.services.scholar.scholar_service"] = original

        result_type, payload = result_queue.get_nowait()
        self.assertEqual(result_type, "success")
        self.assertEqual(payload.get("ok"), True)


if __name__ == "__main__":
    unittest.main()
