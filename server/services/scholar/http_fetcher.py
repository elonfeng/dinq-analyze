"""
HTTP fetching abstractions for Scholar crawling.

目标：
- 统一 retry/backoff/timeout/cache/rate-limit 逻辑
- 支持更“像真人”的访问策略（UA/语言/节奏），核心用于降低封禁概率
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

import hashlib
import os
import random
import threading
import time
import json
from collections import OrderedDict
from contextlib import contextmanager
from urllib.parse import urlparse

from server.services.scholar.cancel import raise_if_cancelled


@dataclass(frozen=True)
class FetcherPolicy:
    max_retries: int = 3
    timeout_seconds: float = 30.0
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 8.0

    # Rate limiting / "human-like" pacing
    min_interval_seconds: float = 3.0
    jitter_seconds: float = 0.6

    # Concurrency limiting (per domain). 0 disables limiting.
    max_inflight_per_domain: int = 1

    # In-memory cache (best-effort)
    cache_ttl_seconds: float = 3600.0
    cache_max_items: int = 256

    # Optional disk cache (for HTML/JSON)
    disk_cache_dir: Optional[str] = None
    disk_cache_ttl_seconds: float = 86400.0  # 1 day

    # Optional quota budget (per user_id + domain + day)
    quota_max_requests_per_day: int = 0  # 0 => disabled
    quota_state_path: Optional[str] = None  # if set, persist to file

    user_agents: Sequence[str] = field(
        default_factory=lambda: (
            # A small, modern UA pool (keep it short and stable).
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        )
    )

    accept_languages: Sequence[str] = field(
        default_factory=lambda: (
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "zh-CN,zh;q=0.9,en;q=0.6",
        )
    )

    referers: Sequence[str] = field(
        default_factory=lambda: (
            "https://scholar.google.com/",
            "https://www.google.com/",
        )
    )


def _sleep_with_cancel(seconds: float, cancel_event: Optional[Any]) -> None:
    if seconds <= 0:
        return
    end = time.time() + seconds
    while time.time() < end:
        raise_if_cancelled(cancel_event)
        time.sleep(min(0.2, end - time.time()))


class RateLimiter:
    def __init__(self, *, min_interval_seconds: float, jitter_seconds: float):
        self._min_interval = max(0.0, float(min_interval_seconds))
        self._jitter = max(0.0, float(jitter_seconds))
        self._lock = threading.Lock()
        self._next_allowed_at = 0.0

    def wait(self, *, cancel_event: Optional[Any], rng: random.Random) -> None:
        if self._min_interval <= 0 and self._jitter <= 0:
            return

        with self._lock:
            now = time.monotonic()
            sleep_for = max(0.0, self._next_allowed_at - now)

            # Reserve the next slot up-front to avoid burst when multiple threads hit.
            interval = self._min_interval
            if self._jitter > 0:
                interval += rng.uniform(0.0, self._jitter)
            self._next_allowed_at = max(self._next_allowed_at, now) + interval

        _sleep_with_cancel(sleep_for, cancel_event)


class InMemoryTTLCache:
    def __init__(self, *, ttl_seconds: float, max_items: int):
        self._ttl = max(0.0, float(ttl_seconds))
        self._max_items = max(0, int(max_items))
        self._lock = threading.Lock()
        self._data: "OrderedDict[str, Any]" = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        if self._ttl <= 0 or self._max_items <= 0:
            return None

        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        if self._ttl <= 0 or self._max_items <= 0:
            return

        now = time.time()
        expires_at = now + self._ttl

        with self._lock:
            self._data[key] = (expires_at, value)
            self._data.move_to_end(key)
            while len(self._data) > self._max_items:
                self._data.popitem(last=False)


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = (parsed.netloc or "").lower()
        return domain
    except Exception:  # noqa: BLE001
        return ""


_FILE_LOCKS: Dict[str, threading.Lock] = {}
_FILE_LOCKS_GUARD = threading.Lock()


def _get_file_lock(path: str) -> threading.Lock:
    with _FILE_LOCKS_GUARD:
        lock = _FILE_LOCKS.get(path)
        if lock is None:
            lock = threading.Lock()
            _FILE_LOCKS[path] = lock
        return lock


class FileDiskCache:
    """
    Very small, best-effort disk cache.

    - Key is hashed to avoid filesystem issues with long URLs
    - TTL uses file mtime (no extra metadata file)
    """

    def __init__(self, *, root_dir: str, ttl_seconds: float):
        self._root_dir = os.path.abspath(root_dir)
        self._ttl = max(0.0, float(ttl_seconds))
        self._lock = _get_file_lock(self._root_dir)
        os.makedirs(self._root_dir, exist_ok=True)

    def _path_for_key(self, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        subdir = os.path.join(self._root_dir, digest[:2])
        return os.path.join(subdir, digest)

    def get_bytes(self, key: str) -> Optional[bytes]:
        if self._ttl <= 0:
            return None

        path = self._path_for_key(key)
        with self._lock:
            try:
                st = os.stat(path)
            except FileNotFoundError:
                return None
            except Exception:  # noqa: BLE001
                return None

            now = time.time()
            if st.st_mtime + self._ttl < now:
                try:
                    os.remove(path)
                except Exception:  # noqa: BLE001
                    pass
                return None

            try:
                with open(path, "rb") as f:
                    return f.read()
            except Exception:  # noqa: BLE001
                return None

    def set_bytes(self, key: str, data: bytes) -> None:
        if self._ttl <= 0:
            return

        path = self._path_for_key(key)
        parent = os.path.dirname(path)
        os.makedirs(parent, exist_ok=True)

        tmp_path = f"{path}.tmp"
        with self._lock:
            try:
                with open(tmp_path, "wb") as f:
                    f.write(data)
                os.replace(tmp_path, path)
            except Exception:  # noqa: BLE001
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:  # noqa: BLE001
                    pass


class QuotaExceeded(Exception):
    def __init__(self, *, user_id: str, domain: str, limit: int):
        super().__init__(f"Quota exceeded for user={user_id!r}, domain={domain!r}, limit={limit}")
        self.user_id = user_id
        self.domain = domain
        self.limit = limit


class DailyQuotaBudget:
    def consume(self, *, user_id: str, domain: str, cost: int = 1) -> None:
        raise NotImplementedError


def _day_key(now_seconds: Optional[float] = None) -> str:
    ts = time.time() if now_seconds is None else float(now_seconds)
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


class InMemoryDailyQuotaBudget(DailyQuotaBudget):
    def __init__(self, *, max_requests_per_day: int):
        self._max = max(0, int(max_requests_per_day))
        self._lock = threading.Lock()
        self._counts: Dict[Tuple[str, str, str], int] = {}

    def consume(self, *, user_id: str, domain: str, cost: int = 1) -> None:
        if self._max <= 0:
            return

        key = (_day_key(), user_id, domain)
        with self._lock:
            current = self._counts.get(key, 0)
            next_value = current + max(1, int(cost))
            if next_value > self._max:
                raise QuotaExceeded(user_id=user_id, domain=domain, limit=self._max)
            self._counts[key] = next_value


class FileDailyQuotaBudget(DailyQuotaBudget):
    """
    Simple file-based budget (best-effort, process-safe via in-process lock).

    File schema:
      {
        "YYYY-MM-DD": { "<user_id>": { "<domain>": count, ... }, ... },
        ...
      }
    """

    def __init__(self, *, path: str, max_requests_per_day: int):
        self._path = os.path.abspath(path)
        self._max = max(0, int(max_requests_per_day))
        self._lock = _get_file_lock(self._path)
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)

    def consume(self, *, user_id: str, domain: str, cost: int = 1) -> None:
        if self._max <= 0:
            return

        day = _day_key()
        cost_i = max(1, int(cost))

        with self._lock:
            data: Dict[str, Any] = {}
            try:
                if os.path.exists(self._path):
                    with open(self._path, "r", encoding="utf-8") as f:
                        data = json.load(f) or {}
            except Exception:  # noqa: BLE001
                data = {}

            day_bucket = data.get(day)
            if not isinstance(day_bucket, dict):
                day_bucket = {}
                data[day] = day_bucket

            user_bucket = day_bucket.get(user_id)
            if not isinstance(user_bucket, dict):
                user_bucket = {}
                day_bucket[user_id] = user_bucket

            current = int(user_bucket.get(domain, 0) or 0)
            next_value = current + cost_i
            if next_value > self._max:
                raise QuotaExceeded(user_id=user_id, domain=domain, limit=self._max)

            user_bucket[domain] = next_value

            # Best effort pruning: keep only today's bucket to avoid file growth.
            for k in list(data.keys()):
                if k != day:
                    data.pop(k, None)

            tmp_path = f"{self._path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp_path, self._path)


class DomainRateLimiter:
    def __init__(self, *, min_interval_seconds: float, jitter_seconds: float):
        self._min_interval = min_interval_seconds
        self._jitter = jitter_seconds
        self._lock = threading.Lock()
        self._limiters: Dict[str, RateLimiter] = {}

    def wait(self, *, domain: str, cancel_event: Optional[Any], rng: random.Random) -> None:
        if not domain:
            domain = "_default"

        with self._lock:
            limiter = self._limiters.get(domain)
            if limiter is None:
                limiter = RateLimiter(min_interval_seconds=self._min_interval, jitter_seconds=self._jitter)
                self._limiters[domain] = limiter

        limiter.wait(cancel_event=cancel_event, rng=rng)


class DomainConcurrencyLimiter:
    def __init__(self, *, max_inflight_per_domain: int):
        self._max = int(max_inflight_per_domain)
        self._lock = threading.Lock()
        self._semaphores: Dict[str, threading.BoundedSemaphore] = {}

    def acquire(self, *, domain: str, cancel_event: Optional[Any]) -> str:
        if self._max <= 0:
            return domain or "_default"

        if not domain:
            domain = "_default"

        with self._lock:
            sem = self._semaphores.get(domain)
            if sem is None:
                sem = threading.BoundedSemaphore(max(1, self._max))
                self._semaphores[domain] = sem

        while True:
            raise_if_cancelled(cancel_event)
            if sem.acquire(timeout=0.2):
                return domain

    def release(self, *, domain: str) -> None:
        if self._max <= 0:
            return

        if not domain:
            domain = "_default"

        with self._lock:
            sem = self._semaphores.get(domain)
        if sem is None:
            return

        try:
            sem.release()
        except ValueError:
            return


_SHARED_DOMAIN_RATE_LIMITERS: Dict[Tuple[float, float], DomainRateLimiter] = {}
_SHARED_DOMAIN_RATE_LIMITERS_LOCK = threading.Lock()


def _get_shared_domain_rate_limiter(*, min_interval_seconds: float, jitter_seconds: float) -> DomainRateLimiter:
    key = (float(min_interval_seconds), float(jitter_seconds))
    with _SHARED_DOMAIN_RATE_LIMITERS_LOCK:
        limiter = _SHARED_DOMAIN_RATE_LIMITERS.get(key)
        if limiter is None:
            limiter = DomainRateLimiter(min_interval_seconds=key[0], jitter_seconds=key[1])
            _SHARED_DOMAIN_RATE_LIMITERS[key] = limiter
        return limiter


_SHARED_DOMAIN_CONCURRENCY_LIMITERS: Dict[int, DomainConcurrencyLimiter] = {}
_SHARED_DOMAIN_CONCURRENCY_LIMITERS_LOCK = threading.Lock()


def _get_shared_domain_concurrency_limiter(*, max_inflight_per_domain: int) -> Optional[DomainConcurrencyLimiter]:
    max_inflight = int(max_inflight_per_domain)
    if max_inflight <= 0:
        return None

    with _SHARED_DOMAIN_CONCURRENCY_LIMITERS_LOCK:
        limiter = _SHARED_DOMAIN_CONCURRENCY_LIMITERS.get(max_inflight)
        if limiter is None:
            limiter = DomainConcurrencyLimiter(max_inflight_per_domain=max_inflight)
            _SHARED_DOMAIN_CONCURRENCY_LIMITERS[max_inflight] = limiter
        return limiter


@contextmanager
def _domain_slot(*, limiter: Optional[DomainConcurrencyLimiter], domain: str, cancel_event: Optional[Any]):
    if limiter is None:
        yield
        return

    acquired_domain = limiter.acquire(domain=domain, cancel_event=cancel_event)
    try:
        yield
    finally:
        limiter.release(domain=acquired_domain)


class _InFlightCall:
    def __init__(self) -> None:
        self.event = threading.Event()
        self.value: Any = None
        self.error: Optional[BaseException] = None


_INFLIGHT_CALLS: Dict[Tuple[str, str, str, int], _InFlightCall] = {}
_INFLIGHT_CALLS_LOCK = threading.Lock()


def _inflight_key(*, kind: str, fetcher: str, url: str, cancel_event: Optional[Any]) -> Tuple[str, str, str, int]:
    group = id(cancel_event) if cancel_event is not None else 0
    return (kind, fetcher, url, group)


def _singleflight(
    key: Tuple[str, str, str, int],
    *,
    cancel_event: Optional[Any],
    fn: Callable[[], Any],
) -> Any:
    with _INFLIGHT_CALLS_LOCK:
        call = _INFLIGHT_CALLS.get(key)
        if call is None:
            call = _InFlightCall()
            _INFLIGHT_CALLS[key] = call
            leader = True
        else:
            leader = False

    if leader:
        try:
            call.value = fn()
        except BaseException as exc:  # noqa: BLE001
            call.error = exc
        finally:
            call.event.set()
            with _INFLIGHT_CALLS_LOCK:
                _INFLIGHT_CALLS.pop(key, None)

        if call.error is not None:
            raise call.error
        return call.value

    while not call.event.wait(timeout=0.2):
        raise_if_cancelled(cancel_event)

    if call.error is not None:
        raise call.error
    return call.value


class HTMLFetcher:
    def fetch_html(
        self,
        url: str,
        *,
        cancel_event: Optional[Any] = None,
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        raise NotImplementedError


class BaseHTMLFetcher(HTMLFetcher):
    def __init__(self, *, policy: FetcherPolicy):
        self._policy = policy
        self._rng = random.Random()
        self._limiter = _get_shared_domain_rate_limiter(
            min_interval_seconds=policy.min_interval_seconds,
            jitter_seconds=policy.jitter_seconds,
        )
        self._concurrency = _get_shared_domain_concurrency_limiter(
            max_inflight_per_domain=policy.max_inflight_per_domain,
        )
        self._cache = InMemoryTTLCache(
            ttl_seconds=policy.cache_ttl_seconds,
            max_items=policy.cache_max_items,
        )
        self._disk_cache = (
            FileDiskCache(root_dir=policy.disk_cache_dir, ttl_seconds=policy.disk_cache_ttl_seconds)
            if policy.disk_cache_dir
            else None
        )
        self._quota_budget: Optional[DailyQuotaBudget] = None
        if policy.quota_max_requests_per_day and policy.quota_max_requests_per_day > 0:
            if policy.quota_state_path:
                self._quota_budget = FileDailyQuotaBudget(
                    path=policy.quota_state_path,
                    max_requests_per_day=policy.quota_max_requests_per_day,
                )
            else:
                self._quota_budget = InMemoryDailyQuotaBudget(
                    max_requests_per_day=policy.quota_max_requests_per_day
                )

    def fetch_html(
        self,
        url: str,
        *,
        cancel_event: Optional[Any] = None,
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        raise_if_cancelled(cancel_event)

        cached = self._cache.get(url)
        if isinstance(cached, str):
            return cached

        if self._disk_cache is not None:
            cached_bytes = self._disk_cache.get_bytes(f"html:{url}")
            if cached_bytes:
                try:
                    cached_text = cached_bytes.decode("utf-8", errors="replace")
                    self._cache.set(url, cached_text)
                    return cached_text
                except Exception:  # noqa: BLE001
                    pass

        def _do_fetch() -> Optional[str]:
            last_exc: Optional[Exception] = None
            domain = _extract_domain(url)
            budget_user_id = user_id or "anonymous"
            for attempt in range(1, max(1, self._policy.max_retries) + 1):
                raise_if_cancelled(cancel_event)
                with _domain_slot(limiter=self._concurrency, domain=domain, cancel_event=cancel_event):
                    self._limiter.wait(domain=domain, cancel_event=cancel_event, rng=self._rng)

                    try:
                        if self._quota_budget is not None:
                            self._quota_budget.consume(user_id=budget_user_id, domain=domain, cost=1)
                        html = self._fetch_once(url, cancel_event=cancel_event)
                        if html:
                            self._cache.set(url, html)
                            if self._disk_cache is not None:
                                self._disk_cache.set_bytes(f"html:{url}", html.encode("utf-8", errors="replace"))
                            return html
                    except QuotaExceeded:
                        raise
                    except Exception as exc:  # noqa: BLE001
                        last_exc = exc

                # Backoff before next attempt
                if attempt < self._policy.max_retries:
                    backoff = min(
                        self._policy.backoff_max_seconds,
                        self._policy.backoff_base_seconds * (2 ** (attempt - 1)),
                    )
                    _sleep_with_cancel(backoff, cancel_event)

            if last_exc is not None:
                # Caller decides logging strategy; keep silent here.
                return None
            return None

        key = _inflight_key(kind="html", fetcher=self.__class__.__name__, url=url, cancel_event=cancel_event)
        html = _singleflight(key, cancel_event=cancel_event, fn=_do_fetch)
        if isinstance(html, str) and html:
            self._cache.set(url, html)
        return html

    def _fetch_once(self, url: str, *, cancel_event: Optional[Any]) -> Optional[str]:
        raise NotImplementedError


class CrawlbaseHTMLFetcher(BaseHTMLFetcher):
    def __init__(self, crawling_api: Any, *, policy: FetcherPolicy):
        super().__init__(policy=policy)
        self._api = crawling_api

    def _fetch_once(self, url: str, *, cancel_event: Optional[Any]) -> Optional[str]:
        raise_if_cancelled(cancel_event)
        response = None
        error: Optional[Exception] = None

        # Crawlbase SDK does not expose request timeouts reliably; enforce a best-effort timeout
        # in a daemon thread so page0 can honor the 10s budget.
        def _call() -> None:
            nonlocal response, error
            try:
                response = self._api.get(url)
            except Exception as exc:  # noqa: BLE001
                error = exc

        t = threading.Thread(target=_call, daemon=True)
        t.start()

        deadline = time.time() + max(0.0, float(self._policy.timeout_seconds))
        while t.is_alive() and time.time() < deadline:
            raise_if_cancelled(cancel_event)
            t.join(timeout=0.2)

        if t.is_alive():
            return None
        if error is not None:
            return None

        # Handle Crawlbase SDK response formats (dict-like and requests-like).
        if isinstance(response, dict) and "headers" in response and "pc_status" in response["headers"]:
            pc_status = str(response["headers"].get("pc_status", ""))
            if pc_status == "200":
                body = response.get("body")
                if isinstance(body, (bytes, bytearray)):
                    return body.decode("utf-8", errors="replace")
                if isinstance(body, str):
                    return body
                return None
            return None

        if hasattr(response, "status_code"):
            if int(getattr(response, "status_code", 0)) == 200:
                return getattr(response, "text", None)
            return None

        if isinstance(response, dict) and "body" in response:
            body = response["body"]
            if isinstance(body, (bytes, bytearray)):
                return body.decode("utf-8", errors="replace")
            if isinstance(body, str):
                return body
            return None

        return None


class FirecrawlHTMLFetcher(BaseHTMLFetcher):
    def __init__(self, firecrawl_app: Any, *, policy: FetcherPolicy):
        super().__init__(policy=policy)
        self._app = firecrawl_app

    def _fetch_once(self, url: str, *, cancel_event: Optional[Any]) -> Optional[str]:
        raise_if_cancelled(cancel_event)
        response = None
        error: Optional[Exception] = None

        def _call() -> None:
            nonlocal response, error
            try:
                response = self._app.scrape_url(
                    url,
                    formats=["html"],
                    onlyMainContent=False,
                )
            except Exception as exc:  # noqa: BLE001
                error = exc

        t = threading.Thread(target=_call, daemon=True)
        t.start()

        deadline = time.time() + max(0.0, float(self._policy.timeout_seconds))
        while t.is_alive() and time.time() < deadline:
            raise_if_cancelled(cancel_event)
            t.join(timeout=0.2)

        if t.is_alive():
            return None
        if error is not None:
            return None
        if response and getattr(response, "html", None):
            return response.html
        return None


class RequestsHTMLFetcher(BaseHTMLFetcher):
    def __init__(self, session: Any, *, policy: FetcherPolicy):
        super().__init__(policy=policy)
        self._session = session

    def _pick_headers(self) -> Dict[str, str]:
        ua = self._rng.choice(list(self._policy.user_agents)) if self._policy.user_agents else ""
        lang = self._rng.choice(list(self._policy.accept_languages)) if self._policy.accept_languages else "en-US,en;q=0.9"
        referer = self._rng.choice(list(self._policy.referers)) if self._policy.referers else "https://scholar.google.com/"
        headers = {
            "User-Agent": ua,
            "Accept-Language": lang,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": referer,
        }
        return {k: v for k, v in headers.items() if v}

    def _fetch_once(self, url: str, *, cancel_event: Optional[Any]) -> Optional[str]:
        raise_if_cancelled(cancel_event)

        # Local import to keep module import light-weight if requests isn't used.
        import requests  # type: ignore

        headers = self._pick_headers()
        resp = self._session.get(
            url,
            headers=headers,
            timeout=self._policy.timeout_seconds,
            allow_redirects=True,
        )
        raise_if_cancelled(cancel_event)

        if resp.status_code == 200:
            return resp.text

        # Treat common throttling statuses as retryable (actual backoff happens in BaseHTMLFetcher).
        if resp.status_code in (429, 500, 502, 503, 504):
            return None

        # Other 4xx are likely not retryable.
        if 400 <= resp.status_code < 500:
            return None

        return None


class JSONFetcher:
    def fetch_json(
        self,
        url: str,
        *,
        cancel_event: Optional[Any] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Any]:
        raise NotImplementedError


class BaseJSONFetcher(JSONFetcher):
    def __init__(self, *, policy: FetcherPolicy):
        self._policy = policy
        self._rng = random.Random()
        self._limiter = _get_shared_domain_rate_limiter(
            min_interval_seconds=policy.min_interval_seconds,
            jitter_seconds=policy.jitter_seconds,
        )
        self._concurrency = _get_shared_domain_concurrency_limiter(
            max_inflight_per_domain=policy.max_inflight_per_domain,
        )
        self._cache = InMemoryTTLCache(
            ttl_seconds=policy.cache_ttl_seconds,
            max_items=policy.cache_max_items,
        )
        self._disk_cache = (
            FileDiskCache(root_dir=policy.disk_cache_dir, ttl_seconds=policy.disk_cache_ttl_seconds)
            if policy.disk_cache_dir
            else None
        )
        self._quota_budget: Optional[DailyQuotaBudget] = None
        if policy.quota_max_requests_per_day and policy.quota_max_requests_per_day > 0:
            if policy.quota_state_path:
                self._quota_budget = FileDailyQuotaBudget(
                    path=policy.quota_state_path,
                    max_requests_per_day=policy.quota_max_requests_per_day,
                )
            else:
                self._quota_budget = InMemoryDailyQuotaBudget(
                    max_requests_per_day=policy.quota_max_requests_per_day
                )

    def fetch_json(
        self,
        url: str,
        *,
        cancel_event: Optional[Any] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Any]:
        raise_if_cancelled(cancel_event)

        cached = self._cache.get(url)
        if cached is not None:
            return cached

        if self._disk_cache is not None:
            cached_bytes = self._disk_cache.get_bytes(f"json:{url}")
            if cached_bytes:
                try:
                    parsed = json.loads(cached_bytes.decode("utf-8", errors="replace"))
                    self._cache.set(url, parsed)
                    return parsed
                except Exception:  # noqa: BLE001
                    pass

        def _do_fetch() -> Optional[Any]:
            last_exc: Optional[Exception] = None
            domain = _extract_domain(url)
            budget_user_id = user_id or "anonymous"
            for attempt in range(1, max(1, self._policy.max_retries) + 1):
                raise_if_cancelled(cancel_event)
                with _domain_slot(limiter=self._concurrency, domain=domain, cancel_event=cancel_event):
                    self._limiter.wait(domain=domain, cancel_event=cancel_event, rng=self._rng)

                    try:
                        if self._quota_budget is not None:
                            self._quota_budget.consume(user_id=budget_user_id, domain=domain, cost=1)
                        payload = self._fetch_once(url, cancel_event=cancel_event)
                        if payload is not None:
                            self._cache.set(url, payload)
                            if self._disk_cache is not None:
                                try:
                                    self._disk_cache.set_bytes(
                                        f"json:{url}",
                                        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                    )
                                except Exception:  # noqa: BLE001
                                    pass
                            return payload
                    except QuotaExceeded:
                        raise
                    except Exception as exc:  # noqa: BLE001
                        last_exc = exc

                if attempt < self._policy.max_retries:
                    backoff = min(
                        self._policy.backoff_max_seconds,
                        self._policy.backoff_base_seconds * (2 ** (attempt - 1)),
                    )
                    _sleep_with_cancel(backoff, cancel_event)

            if last_exc is not None:
                return None
            return None

        key = _inflight_key(kind="json", fetcher=self.__class__.__name__, url=url, cancel_event=cancel_event)
        payload = _singleflight(key, cancel_event=cancel_event, fn=_do_fetch)
        if payload is not None:
            self._cache.set(url, payload)
        return payload

    def _fetch_once(self, url: str, *, cancel_event: Optional[Any]) -> Optional[Any]:
        raise NotImplementedError


class RequestsJSONFetcher(BaseJSONFetcher):
    def __init__(self, session: Any, *, policy: FetcherPolicy):
        super().__init__(policy=policy)
        self._session = session

    def _pick_headers(self) -> Dict[str, str]:
        ua = self._rng.choice(list(self._policy.user_agents)) if self._policy.user_agents else ""
        lang = self._rng.choice(list(self._policy.accept_languages)) if self._policy.accept_languages else "en-US,en;q=0.9"
        referer = self._rng.choice(list(self._policy.referers)) if self._policy.referers else "https://scholar.google.com/"
        headers = {
            "User-Agent": ua,
            "Accept-Language": lang,
            "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
            "Referer": referer,
        }
        return {k: v for k, v in headers.items() if v}

    def _fetch_once(self, url: str, *, cancel_event: Optional[Any]) -> Optional[Any]:
        raise_if_cancelled(cancel_event)

        import requests  # type: ignore

        headers = self._pick_headers()
        resp = self._session.get(
            url,
            headers=headers,
            timeout=self._policy.timeout_seconds,
            allow_redirects=True,
        )
        raise_if_cancelled(cancel_event)

        if resp.status_code == 200:
            try:
                return resp.json()
            except Exception:  # noqa: BLE001
                # Some endpoints return JSON-like text; try fallback parsing.
                try:
                    return json.loads(resp.text or "")
                except Exception:  # noqa: BLE001
                    return None

        if resp.status_code in (429, 500, 502, 503, 504):
            return None

        if 400 <= resp.status_code < 500:
            return None

        return None
