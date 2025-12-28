import json
import os
import unittest


try:
    from server.config.env_loader import load_environment_variables

    load_environment_variables(log_dinq_vars=False)
except Exception:
    pass


def _enabled(name: str) -> bool:
    return os.getenv(name, "false").lower() in ("1", "true", "yes", "on")

def _present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


RUN_SMOKE = _enabled("DINQ_RUN_ONLINE_SMOKE")
BASE_URL = os.getenv("DINQ_SMOKE_BASE_URL", "http://127.0.0.1:5001").rstrip("/")


@unittest.skipUnless(RUN_SMOKE, "DINQ_RUN_ONLINE_SMOKE not enabled")
class TestOnlineSmoke(unittest.TestCase):
    def test_health(self):
        import requests  # type: ignore

        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "ok")

    @unittest.skipUnless(os.getenv("GITHUB_TOKEN"), "GITHUB_TOKEN not set")
    def test_github_health(self):
        import requests  # type: ignore

        resp = requests.get(f"{BASE_URL}/api/github/health", timeout=10)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "healthy")

    @unittest.skipUnless(os.getenv("GITHUB_TOKEN"), "GITHUB_TOKEN not set")
    def test_github_stream_returns_events(self):
        import requests  # type: ignore

        headers = {"Content-Type": "application/json", "Userid": "smoke_user", "Accept": "text/event-stream"}
        resp = requests.post(
            f"{BASE_URL}/api/github/analyze-stream",
            headers=headers,
            json={"username": "octocat"},
            stream=True,
            timeout=30,
        )
        self.assertEqual(resp.status_code, 200)

        events = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line[len("data: ") :])
            events.append(payload)
            if len(events) >= 5:
                break

        self.assertTrue(events, "expected at least one SSE event")
        self.assertTrue(all(e.get("source") == "github" for e in events))

    @unittest.skipUnless(_enabled("DINQ_SMOKE_SCHOLAR"), "DINQ_SMOKE_SCHOLAR not enabled")
    def test_scholar_stream_starts(self):
        """
        Scholar 外部依赖更不稳定（易限速/封禁/超时），默认不跑。
        """
        import requests  # type: ignore

        headers = {"Content-Type": "application/json", "Userid": "smoke_user", "Accept": "text/event-stream"}
        resp = requests.post(
            f"{BASE_URL}/api/stream",
            headers=headers,
            json={"query": "Y-ql3zMAAAAJ"},
            stream=True,
            timeout=60,
        )
        self.assertEqual(resp.status_code, 200)

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line[len("data: ") :])
            # 任意进度/开始事件即可判定链路通了
            if payload.get("source") == "scholar" and payload.get("event_type") in ("start", "progress", "data", "ping"):
                return

        raise AssertionError("did not receive any scholar SSE events")

    @unittest.skipUnless(_enabled("DINQ_SMOKE_SCHOLAR_PK"), "DINQ_SMOKE_SCHOLAR_PK not enabled")
    @unittest.skipUnless(_present("CRAWLBASE_API_TOKEN") or _present("CRAWLBASE_TOKEN"), "CRAWLBASE_API_TOKEN not set")
    @unittest.skipUnless(_present("OPENROUTER_API_KEY") or _present("OPENROUTER_KEY") or _present("GENERIC_OPENROUTER_API_KEY"), "OPENROUTER_API_KEY not set")
    @unittest.skipUnless(_present("KIMI_API_KEY"), "KIMI_API_KEY not set")
    def test_scholar_pk_emits_pkdata(self):
        import requests  # type: ignore

        headers = {"Content-Type": "application/json", "Userid": "smoke_user", "Accept": "text/event-stream"}
        resp = requests.post(
            f"{BASE_URL}/api/scholar-pk",
            headers=headers,
            json={"researcher1": "Y-ql3zMAAAAJ", "researcher2": "ZUeyIxMAAAAJ"},
            stream=True,
            timeout=120,
        )
        self.assertEqual(resp.status_code, 200)

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line[len("data: ") :])
            if payload.get("source") != "scholar":
                continue
            if payload.get("type") == "pkData" or payload.get("event_type") == "data" and payload.get("step") == "pk_result":
                pk = payload.get("payload") or payload.get("content") or {}
                self.assertIn("researcher1", pk)
                self.assertIn("researcher2", pk)
                return

        raise AssertionError("did not receive pkData event")


if __name__ == "__main__":
    unittest.main()
