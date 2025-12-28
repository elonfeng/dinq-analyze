import json
import os
import unittest
from unittest.mock import patch


def _collect_sse_events(response) -> list:
    raw = b"".join(response.response).decode("utf-8", errors="replace")
    events = []
    for line in raw.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :].strip()))
    return events


class TestStreamingEndpointsOffline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure test bypass is enabled before importing the full app.
        os.environ.setdefault("DINQ_AUTH_BYPASS", "true")
        os.environ.setdefault("DINQ_EMAIL_BACKEND", "noop")

        from server.app import app as flask_app

        cls.app = flask_app

    def setUp(self):
        self.client = self.app.test_client()

    def test_scholar_stream_endpoint_emits_progress_and_end(self):
        def dummy_builder(*, query, active_sessions, user_id, trace_id=None, job_manager=None, **_kwargs):
            def task_fn(progress_cb, result_queue, cancel_event=None):
                progress_cb({"event_type": "progress", "message": f"query={query}"})
                result_queue.put(("success", {"ok": True, "query": query, "user_id": user_id}))

            return task_fn

        with patch("server.app.build_scholar_task_fn", side_effect=dummy_builder):
            resp = self.client.post(
                "/api/stream",
                json={"query": "offline_test", "legacy": True},
                headers={"Userid": "u_offline"},
            )

        self.assertEqual(resp.status_code, 200)
        events = _collect_sse_events(resp)
        self.assertTrue(any(e.get("event_type") == "progress" for e in events))
        self.assertEqual(events[-1].get("event_type"), "end")

    def test_scholar_pk_endpoint_emits_pkdata_and_end(self):
        def dummy_pk_builder(query1, query2, *, user_id=None, trace_id=None):
            def task_fn(progress_cb, result_queue, cancel_event=None):
                progress_cb(
                    {
                        "event_type": "data",
                        "type": "pkData",
                        "payload": {"researcher1": query1, "researcher2": query2, "roast": "ok"},
                        "content": {"researcher1": query1, "researcher2": query2, "roast": "ok"},
                    }
                )
                result_queue.put(("success", {"ok": True}))

            return task_fn

        with patch("server.app.build_pk_task_fn", side_effect=dummy_pk_builder):
            resp = self.client.post(
                "/api/scholar-pk",
                json={"researcher1": "A", "researcher2": "B"},
                headers={"Userid": "u_offline"},
            )

        self.assertEqual(resp.status_code, 200)
        events = _collect_sse_events(resp)
        self.assertTrue(any(e.get("type") == "pkData" for e in events))
        self.assertEqual(events[-1].get("event_type"), "end")

    def test_github_analyze_stream_endpoint_offline_stub(self):
        def stub_build_stream_task_fn(**_kwargs):
            def task_fn(progress_cb, result_queue, cancel_event=None):
                progress_cb({"event_type": "progress", "message": "github stub"})
                result_queue.put(("success", {"ok": True}))

            return task_fn

        with patch("server.api.github_analyzer_api.build_stream_task_fn", side_effect=stub_build_stream_task_fn):
            resp = self.client.post(
                "/api/github/analyze-stream",
                json={"username": "octocat"},
                headers={"Userid": "u_offline"},
            )

        self.assertEqual(resp.status_code, 200)
        events = _collect_sse_events(resp)
        self.assertTrue(any(e.get("event_type") == "progress" for e in events))
        self.assertEqual(events[-1].get("event_type"), "end")
