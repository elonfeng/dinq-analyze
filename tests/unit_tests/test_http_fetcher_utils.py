import os
import random
import tempfile
import time
import threading
import unittest
from unittest.mock import patch

from server.services.scholar.http_fetcher import (
    BaseHTMLFetcher,
    FileDailyQuotaBudget,
    FileDiskCache,
    FetcherPolicy,
    InMemoryDailyQuotaBudget,
    InMemoryTTLCache,
    QuotaExceeded,
    RateLimiter,
)
from server.services.scholar.cancel import ScholarTaskCancelled


class TestInMemoryTTLCache(unittest.TestCase):
    def test_set_get_and_expire(self):
        cache = InMemoryTTLCache(ttl_seconds=10, max_items=10)

        with patch("server.services.scholar.http_fetcher.time.time") as now:
            now.return_value = 100.0
            cache.set("k1", "v1")
            self.assertEqual(cache.get("k1"), "v1")

            now.return_value = 111.0
            self.assertIsNone(cache.get("k1"))

    def test_lru_eviction(self):
        cache = InMemoryTTLCache(ttl_seconds=100, max_items=2)

        with patch("server.services.scholar.http_fetcher.time.time", return_value=100.0):
            cache.set("a", 1)
            cache.set("b", 2)
            cache.set("c", 3)

            self.assertIsNone(cache.get("a"))
            self.assertEqual(cache.get("b"), 2)
            self.assertEqual(cache.get("c"), 3)


class TestRateLimiter(unittest.TestCase):
    def test_wait_reserves_next_slot(self):
        limiter = RateLimiter(min_interval_seconds=1.0, jitter_seconds=0.0)
        rng = random.Random(0)

        with patch("server.services.scholar.http_fetcher.time.monotonic") as monotonic, patch(
            "server.services.scholar.http_fetcher._sleep_with_cancel"
        ) as sleep_with_cancel:
            monotonic.side_effect = [0.0, 0.0]

            limiter.wait(cancel_event=None, rng=rng)
            limiter.wait(cancel_event=None, rng=rng)

            self.assertEqual(len(sleep_with_cancel.call_args_list), 2)
            self.assertAlmostEqual(sleep_with_cancel.call_args_list[0].args[0], 0.0, places=6)
            self.assertAlmostEqual(sleep_with_cancel.call_args_list[1].args[0], 1.0, places=6)


class TestFileDiskCache(unittest.TestCase):
    def test_set_get_and_expire(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileDiskCache(root_dir=tmp, ttl_seconds=1.0)
            cache.set_bytes("k1", b"v1")
            self.assertEqual(cache.get_bytes("k1"), b"v1")

            # Jump into the future; mtime is real, but time.time() is used for TTL checks.
            now = time.time()
            with patch("server.services.scholar.http_fetcher.time.time", return_value=now + 10.0):
                self.assertIsNone(cache.get_bytes("k1"))


class TestQuotaBudget(unittest.TestCase):
    def test_in_memory_budget(self):
        budget = InMemoryDailyQuotaBudget(max_requests_per_day=2)
        budget.consume(user_id="u1", domain="example.com")
        budget.consume(user_id="u1", domain="example.com")
        with self.assertRaises(QuotaExceeded):
            budget.consume(user_id="u1", domain="example.com")

    def test_file_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "quota.json")
            budget = FileDailyQuotaBudget(path=path, max_requests_per_day=1)
            with patch("server.services.scholar.http_fetcher._day_key", return_value="2025-01-01"):
                budget.consume(user_id="u1", domain="example.com")
                with self.assertRaises(QuotaExceeded):
                    budget.consume(user_id="u1", domain="example.com")


class _DummyHTMLFetcher(BaseHTMLFetcher):
    def __init__(self, *, policy: FetcherPolicy):
        super().__init__(policy=policy)
        self.fetch_once_calls = 0
        self.fetch_started = threading.Event()
        self.allow_finish = threading.Event()

    def _fetch_once(self, url: str, *, cancel_event=None):
        self.fetch_once_calls += 1
        self.fetch_started.set()
        while not self.allow_finish.wait(timeout=0.05):
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                raise ScholarTaskCancelled("Canceled")
        return "<html>ok</html>"


class _TwoCallHTMLFetcher(BaseHTMLFetcher):
    def __init__(self, *, policy: FetcherPolicy):
        super().__init__(policy=policy)
        self.fetch_once_calls = 0
        self.started1 = threading.Event()
        self.started2 = threading.Event()
        self.finish1 = threading.Event()
        self.finish2 = threading.Event()
        self._lock = threading.Lock()

    def _fetch_once(self, url: str, *, cancel_event=None):
        with self._lock:
            self.fetch_once_calls += 1
            idx = self.fetch_once_calls

        if idx == 1:
            self.started1.set()
            if not self.finish1.wait(timeout=1.0):
                raise AssertionError("Timeout waiting for finish1")
            return "<html>1</html>"
        if idx == 2:
            self.started2.set()
            if not self.finish2.wait(timeout=1.0):
                raise AssertionError("Timeout waiting for finish2")
            return "<html>2</html>"

        raise AssertionError("Unexpected extra call")


class TestSingleFlight(unittest.TestCase):
    def test_dedupes_concurrent_same_cancel_group(self):
        policy = FetcherPolicy(
            max_retries=1,
            timeout_seconds=1.0,
            backoff_base_seconds=0.0,
            backoff_max_seconds=0.0,
            min_interval_seconds=0.0,
            jitter_seconds=0.0,
            max_inflight_per_domain=0,
            cache_ttl_seconds=0.0,
            cache_max_items=0,
        )
        fetcher = _DummyHTMLFetcher(policy=policy)
        cancel_event = threading.Event()
        url = "https://example.com/page"

        results = []
        errors = []

        def worker():
            try:
                results.append(fetcher.fetch_html(url, cancel_event=cancel_event, user_id="u1"))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = threading.Thread(target=worker)
        t1.start()
        self.assertTrue(fetcher.fetch_started.wait(timeout=1.0))

        t2 = threading.Thread(target=worker)
        t2.start()

        try:
            time.sleep(0.1)
        finally:
            fetcher.allow_finish.set()

        t1.join(timeout=2.0)
        t2.join(timeout=2.0)
        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())

        if errors:
            raise errors[0]

        self.assertEqual(fetcher.fetch_once_calls, 1)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r == "<html>ok</html>" for r in results))

    def test_separates_inflight_by_cancel_event_group(self):
        policy = FetcherPolicy(
            max_retries=1,
            timeout_seconds=1.0,
            backoff_base_seconds=0.0,
            backoff_max_seconds=0.0,
            min_interval_seconds=0.0,
            jitter_seconds=0.0,
            max_inflight_per_domain=0,
            cache_ttl_seconds=0.0,
            cache_max_items=0,
        )
        fetcher = _TwoCallHTMLFetcher(policy=policy)
        url = "https://example.com/page"

        cancel1 = threading.Event()
        cancel2 = threading.Event()

        def worker(cancel_event):
            fetcher.fetch_html(url, cancel_event=cancel_event, user_id="u1")

        t1 = threading.Thread(target=worker, args=(cancel1,))
        t1.start()
        self.assertTrue(fetcher.started1.wait(timeout=1.0))

        t2 = threading.Thread(target=worker, args=(cancel2,))
        t2.start()

        # If singleflight incorrectly dedupes across cancel_event groups,
        # the second call won't enter _fetch_once while the first is blocked.
        self.assertTrue(fetcher.started2.wait(timeout=1.0))

        fetcher.finish2.set()
        fetcher.finish1.set()

        t1.join(timeout=2.0)
        t2.join(timeout=2.0)
        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())

        self.assertEqual(fetcher.fetch_once_calls, 2)


if __name__ == "__main__":
    unittest.main()
