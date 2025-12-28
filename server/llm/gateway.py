"""LLM Gateway: routing, cache, JSON repair, streaming delta."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests
from requests.adapters import HTTPAdapter
try:
    from json_repair import repair_json
except Exception:  # noqa: BLE001
    def repair_json(text: str) -> str:
        return text

from server.config.api_keys import get_groq_api_key, get_openrouter_api_key
from server.config.llm_models import get_default_model, resolve_task_model
from server.llm.cache import LLMCacheStore
from server.llm.context import get_llm_stream_context
from server.utils.timing import elapsed_ms, now_perf

logger = logging.getLogger(__name__)


DEFAULT_MODEL = get_default_model()

_BUILTIN_TASK_ROUTES: dict[str, str] = {
    # Tail-latency killers (Groq primary + Gemini Flash hedge).
    "linkedin_roast": "groq:llama-3.1-8b-instant,openrouter:google/gemini-2.5-flash",
    "researcher_evaluation": "groq:llama-3.1-8b-instant,openrouter:google/gemini-2.5-flash",
}

_BUILTIN_HEDGE_TASKS: set[str] = {
    # Non-JSON tasks that benefit from racing providers for lower p95.
    "researcher_evaluation",
}


@dataclass(frozen=True)
class RouteSpec:
    provider: str
    model: str

    def key(self) -> str:
        p = str(self.provider or "").strip().lower() or "openrouter"
        return f"{p}:{str(self.model or '').strip()}"


@dataclass
class AttemptResult:
    route: RouteSpec
    duration_ms: int
    ok: bool
    http_status: Optional[int] = None
    error_type: str = ""
    exc: Optional[Exception] = None
    text: str = ""
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None

    parsed_json: Any = None
    valid_json: bool = False


def _task_key(task: Optional[str]) -> str:
    raw = str(task or "").strip()
    if not raw:
        return ""
    return re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").upper()


def _env_task_routes(task: Optional[str]) -> str:
    return f"DINQ_LLM_TASK_ROUTES_{_task_key(task)}"


def _env_task_policy(task: Optional[str]) -> str:
    return f"DINQ_LLM_TASK_POLICY_{_task_key(task)}"


def _env_task_hedge_delay_ms(task: Optional[str]) -> str:
    return f"DINQ_LLM_TASK_HEDGE_DELAY_MS_{_task_key(task)}"


def _parse_route_spec(spec: str, *, default_provider: str = "openrouter") -> Optional[RouteSpec]:
    s = str(spec or "").strip()
    if not s:
        return None
    if ":" in s:
        prefix, rest = s.split(":", 1)
        p = prefix.strip().lower()
        if p in ("openrouter", "groq"):
            m = rest.strip()
            if not m:
                return None
            return RouteSpec(provider=p, model=m)
    # Backward-compatible: plain model id implies OpenRouter.
    return RouteSpec(provider=str(default_provider or "openrouter").strip().lower(), model=s)


def _parse_routes(raw: str, *, default_provider: str = "openrouter") -> list[RouteSpec]:
    out: list[RouteSpec] = []
    for part in str(raw or "").split(","):
        r = _parse_route_spec(part, default_provider=default_provider)
        if r is None:
            continue
        out.append(r)
    # De-dupe while preserving order.
    seen: set[str] = set()
    deduped: list[RouteSpec] = []
    for r in out:
        k = r.key()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)
    return deduped


class LLMGateway:
    def __init__(self) -> None:
        self._cache = LLMCacheStore()
        self._router: Dict[str, str] = {}
        self._session_local = threading.local()
        self._breaker_lock = threading.Lock()
        self._breaker_failures: Dict[str, int] = {}
        self._breaker_open_until: Dict[str, float] = {}
        self._hedge_lock = threading.Lock()
        self._hedge_executor: Optional[ThreadPoolExecutor] = None
        self._provider_sem_lock = threading.Lock()
        self._provider_semaphores: Dict[str, threading.Semaphore] = {}

    def _get_session(self) -> requests.Session:
        sess = getattr(self._session_local, "session", None)
        if sess is not None:
            return sess
        sess = requests.Session()
        try:
            pool_max = int(os.getenv("DINQ_LLM_HTTP_POOL_MAXSIZE", "32") or "32")
        except Exception:
            pool_max = 32
        pool_max = max(4, min(int(pool_max), 256))
        try:
            sess.mount("https://", HTTPAdapter(pool_connections=pool_max, pool_maxsize=pool_max, max_retries=0))
            sess.mount("http://", HTTPAdapter(pool_connections=pool_max, pool_maxsize=pool_max, max_retries=0))
        except Exception:
            pass
        self._session_local.session = sess
        return sess

    def _get_hedge_executor(self) -> ThreadPoolExecutor:
        if self._hedge_executor is not None:
            return self._hedge_executor
        with self._hedge_lock:
            if self._hedge_executor is not None:
                return self._hedge_executor
            try:
                raw = int(os.getenv("DINQ_LLM_HEDGE_MAX_WORKERS", "8") or "8")
            except Exception:
                raw = 8
            max_workers = max(1, min(int(raw), 64))
            self._hedge_executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="dinq-llm-hedge")
            return self._hedge_executor

    def _provider_max_concurrency(self, provider: str) -> int:
        p = str(provider or "").strip().lower() or "openrouter"
        env = f"DINQ_LLM_{p.upper()}_MAX_CONCURRENCY"
        raw = os.getenv(env)
        if raw is None:
            return 0
        try:
            return max(0, min(int(raw), 2048))
        except Exception:
            return 0

    def _get_provider_semaphore(self, provider: str) -> Optional[threading.Semaphore]:
        limit = self._provider_max_concurrency(provider)
        if limit <= 0:
            return None
        p = str(provider or "").strip().lower() or "openrouter"
        with self._provider_sem_lock:
            sem = self._provider_semaphores.get(p)
            if sem is None:
                sem = threading.Semaphore(limit)
                self._provider_semaphores[p] = sem
            return sem

    def _breaker_key(self, *, route: RouteSpec) -> str:
        # Per-route breaker (provider+model).
        return route.key() or "default"

    def _breaker_config(self) -> tuple[bool, int, float]:
        enabled_raw = os.getenv("DINQ_LLM_CIRCUIT_BREAKER_ENABLED")
        enabled = True if enabled_raw is None else str(enabled_raw).strip().lower() in ("1", "true", "yes", "on")
        try:
            fail_threshold = int(os.getenv("DINQ_LLM_CIRCUIT_BREAKER_FAIL_THRESHOLD", "5") or "5")
        except Exception:
            fail_threshold = 5
        fail_threshold = max(1, min(int(fail_threshold), 50))
        try:
            cooldown = float(os.getenv("DINQ_LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "20") or "20")
        except Exception:
            cooldown = 20.0
        cooldown = max(1.0, min(float(cooldown), 600.0))
        return enabled, fail_threshold, cooldown

    def _breaker_check(self, *, key: str) -> None:
        enabled, _, _ = self._breaker_config()
        if not enabled:
            return
        now = time.monotonic()
        with self._breaker_lock:
            until = float(self._breaker_open_until.get(key) or 0.0)
            if until and now < until:
                raise RuntimeError("LLM circuit breaker open")

    def _breaker_record_success(self, *, key: str) -> None:
        with self._breaker_lock:
            self._breaker_failures.pop(key, None)
            self._breaker_open_until.pop(key, None)

    def _breaker_record_failure(self, *, key: str) -> None:
        enabled, fail_threshold, cooldown = self._breaker_config()
        if not enabled:
            return
        now = time.monotonic()
        with self._breaker_lock:
            cur = int(self._breaker_failures.get(key) or 0) + 1
            self._breaker_failures[key] = cur
            if cur >= int(fail_threshold):
                self._breaker_open_until[key] = now + float(cooldown)

    def register_route(self, task: str, model: str) -> None:
        self._router[task] = model

    def _resolve_model(self, task: Optional[str], model: Optional[str]) -> str:
        if model:
            return model
        env_override = resolve_task_model(task)
        if env_override:
            return env_override
        if task and task in self._router:
            return self._router[task]
        return DEFAULT_MODEL

    def _hash_messages(
        self,
        route_key: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        extra: Optional[Dict[str, Any]],
    ) -> str:
        raw = json.dumps(
            {
                "route": str(route_key or ""),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "extra": extra or {},
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _parse_json(self, text: str) -> Any:
        def _strip_code_fences(s: str) -> str:
            t = str(s or "").strip()
            if not t:
                return ""
            m = re.match(r"^```(?:json)?\\s*(.*?)\\s*```$", t, flags=re.IGNORECASE | re.DOTALL)
            if m:
                return str(m.group(1) or "").strip()
            return t

        def _extract_bracketed(s: str) -> str:
            t = str(s or "").strip()
            if not t:
                return ""
            candidates: list[str] = []
            for open_ch, close_ch in (("{", "}"), ("[", "]")):
                start = t.find(open_ch)
                end = t.rfind(close_ch)
                if 0 <= start < end:
                    candidates.append(t[start : end + 1])
            if not candidates:
                return t
            # Prefer the longest candidate (often the full JSON object).
            return max(candidates, key=len)

        cleaned = _strip_code_fences(text)
        try:
            return json.loads(cleaned)
        except Exception:
            try:
                repaired = repair_json(cleaned)
                return json.loads(repaired)
            except Exception:
                try:
                    extracted = _extract_bracketed(cleaned)
                    return json.loads(extracted)
                except Exception:
                    return None

    def _resolve_routes(self, *, task: Optional[str], model: Optional[str]) -> list[RouteSpec]:
        # 1) Explicit model passed by caller (supports provider:model)
        if model:
            r = _parse_route_spec(model)
            return [r] if r is not None else []

        # 2) Per-task multi-route override (comma-separated)
        env_routes = os.getenv(_env_task_routes(task))
        if env_routes:
            parsed = _parse_routes(env_routes)
            if parsed:
                return parsed

        # 3) Built-in multi-route defaults for tail-latency-sensitive tasks.
        if task:
            builtin_routes = _BUILTIN_TASK_ROUTES.get(str(task))
            if builtin_routes:
                parsed = _parse_routes(builtin_routes)
                if parsed:
                    return parsed

        # 4) Existing per-task model override / default model
        resolved_model = self._resolve_model(task, None)
        r = _parse_route_spec(resolved_model)
        return [r] if r is not None else []

    def _resolve_policy(self, *, task: Optional[str], routes: list[RouteSpec], expect_json: bool, stream: bool) -> str:
        if stream or len(routes) <= 1:
            return "single"
        raw = os.getenv(_env_task_policy(task))
        if raw:
            v = str(raw).strip().lower()
            if v in ("single", "fallback", "hedge"):
                return v
        if task and str(task) in _BUILTIN_HEDGE_TASKS:
            return "hedge"
        # Default: hedge strict JSON tasks; otherwise fallback.
        return "hedge" if expect_json else "fallback"

    def _hedge_delay_ms(self, *, task: Optional[str]) -> int:
        raw = os.getenv(_env_task_hedge_delay_ms(task))
        if raw is None:
            raw = os.getenv("DINQ_LLM_HEDGE_DELAY_MS", "350")
        try:
            ms = int(raw or 0)
        except Exception:
            ms = 350
        return max(0, min(int(ms), 5000))

    def _provider_url(self, provider: str) -> str:
        p = str(provider or "").strip().lower() or "openrouter"
        if p == "groq":
            base = str(os.getenv("DINQ_GROQ_BASE_URL", "https://api.groq.com/openai/v1") or "").strip()
            base = base.rstrip("/")
            return f"{base}/chat/completions"
        base = str(os.getenv("DINQ_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1") or "").strip()
        base = base.rstrip("/")
        return f"{base}/chat/completions"

    def _headers_for_route(self, route: RouteSpec) -> dict[str, str]:
        if route.provider == "groq":
            api_key = get_groq_api_key()
            if not api_key:
                raise RuntimeError("Missing Groq API key")
            return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        api_key = get_openrouter_api_key()
        if not api_key:
            raise RuntimeError("Missing OpenRouter API key")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("DINQ_HTTP_REFERER", "https://dinq.ai"),
        }
        title = os.getenv("DINQ_OPENROUTER_APP_TITLE")
        if title:
            headers["X-Title"] = str(title)
        return headers

    def _extract_text_and_usage(self, data: Any) -> tuple[str, Optional[int], Optional[int]]:
        if not isinstance(data, dict):
            return "", None, None
        text = ""
        try:
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0] if isinstance(choices[0], dict) else {}
                msg = first.get("message") if isinstance(first, dict) else {}
                if isinstance(msg, dict):
                    text = str(msg.get("content") or "")
                elif isinstance(first, dict) and first.get("text") is not None:
                    text = str(first.get("text") or "")
        except Exception:
            text = ""

        tokens_in = None
        tokens_out = None
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        for k in ("prompt_tokens", "input_tokens"):
            if usage.get(k) is not None:
                try:
                    tokens_in = int(usage.get(k) or 0)
                except Exception:
                    tokens_in = None
                break
        for k in ("completion_tokens", "output_tokens"):
            if usage.get(k) is not None:
                try:
                    tokens_out = int(usage.get(k) or 0)
                except Exception:
                    tokens_out = None
                break
        return text, tokens_in, tokens_out

    def _request_route(
        self,
        *,
        route: RouteSpec,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        stream: bool,
        stream_callback: Optional[Callable[[str], None]],
        extra: Optional[Dict[str, Any]],
        timeout_seconds: Optional[float],
    ) -> AttemptResult:
        url = self._provider_url(route.provider)
        headers = self._headers_for_route(route)
        payload: Dict[str, Any] = {
            "model": route.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": bool(stream),
        }
        if extra:
            payload.update(extra)

        sem = self._get_provider_semaphore(route.provider)
        acquired = False
        if sem is not None:
            try:
                acquired = bool(sem.acquire(timeout=max(0.1, float(timeout_seconds or 60))))
            except Exception:
                acquired = False
            if not acquired:
                return AttemptResult(route=route, duration_ms=0, ok=False, http_status=None, error_type="concurrency_timeout", exc=None)

        t0 = now_perf()
        breaker_key = self._breaker_key(route=route)

        try:
            if stream:
                if route.provider not in ("openrouter", "groq"):
                    return AttemptResult(route=route, duration_ms=0, ok=False, error_type="stream_unsupported", exc=None)
                text = self._stream_openai_compatible(
                    route=route,
                    url=url,
                    headers=headers,
                    payload=payload,
                    stream_callback=stream_callback,
                    timeout_seconds=timeout_seconds,
                )
                return AttemptResult(route=route, duration_ms=elapsed_ms(t0), ok=True, http_status=200, text=text)

            self._breaker_check(key=breaker_key)
            try:
                max_attempts = int(os.getenv("DINQ_LLM_HTTP_MAX_ATTEMPTS", "1") or "1")
            except Exception:
                max_attempts = 1
            max_attempts = max(1, min(int(max_attempts), 5))

            last_exc: Optional[Exception] = None
            last_status: Optional[int] = None
            last_error_type: str = ""

            for attempt in range(max_attempts):
                try:
                    response = self._get_session().post(url, headers=headers, json=payload, timeout=timeout_seconds or 60)
                    status = int(getattr(response, "status_code", 0) or 0)
                    last_status = status
                    if status in (429,) or (500 <= status <= 599):
                        raise requests.HTTPError(f"retryable_status:{status}", response=response)
                    response.raise_for_status()
                    data = response.json() if response.text else {}
                    text, tokens_in, tokens_out = self._extract_text_and_usage(data)
                    self._breaker_record_success(key=breaker_key)
                    return AttemptResult(
                        route=route,
                        duration_ms=elapsed_ms(t0),
                        ok=True,
                        http_status=status,
                        text=text,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                    )
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    retryable = False
                    status = 0
                    if isinstance(exc, requests.HTTPError):
                        try:
                            resp = exc.response
                            status = int(getattr(resp, "status_code", 0) or 0) if resp is not None else 0
                        except Exception:
                            status = 0
                        retryable = status in (429,) or (500 <= status <= 599)
                        last_error_type = f"http_{status}" if status else "http_error"
                    elif isinstance(exc, requests.exceptions.Timeout):
                        retryable = True
                        last_error_type = "timeout"
                    elif isinstance(exc, requests.exceptions.ConnectionError):
                        retryable = True
                        last_error_type = "connection_error"
                    else:
                        last_error_type = f"error:{type(exc).__name__}"

                    if retryable:
                        self._breaker_record_failure(key=breaker_key)
                    else:
                        self._breaker_record_success(key=breaker_key)

                    if (not retryable) or (attempt + 1 >= max_attempts):
                        break
                    sleep_s = min(2.0, 0.2 * (2**attempt)) + random.random() * 0.1
                    try:
                        time.sleep(sleep_s)
                    except Exception:
                        pass

            return AttemptResult(
                route=route,
                duration_ms=elapsed_ms(t0),
                ok=False,
                http_status=last_status,
                error_type=last_error_type or ("error" if last_exc else "unknown"),
                exc=last_exc,
            )
        finally:
            if sem is not None and acquired:
                try:
                    sem.release()
                except Exception:
                    pass

    def chat(
        self,
        *,
        task: Optional[str],
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        expect_json: bool = False,
        stream: bool = False,
        stream_callback: Optional[Callable[[str], None]] = None,
        cache: bool = True,
        extra: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> Any:
        context_callback, force_stream = get_llm_stream_context()
        if stream_callback is None and context_callback is not None:
            stream_callback = context_callback
            if force_stream:
                stream = True

        routes = self._resolve_routes(task=task, model=model)
        if not routes:
            raise RuntimeError("No LLM routes configured")

        policy = self._resolve_policy(task=task, routes=routes, expect_json=expect_json, stream=stream)
        primary = routes[0]
        cache_key = self._hash_messages(primary.key(), messages, temperature, max_tokens, extra)

        if cache:
            t_cache = now_perf()
            cached = self._cache.get(cache_key)
            if cached:
                total_ms = elapsed_ms(t_cache)
                try:
                    slow_ms = int(os.getenv("DINQ_LLM_LOG_SLOW_MS", "4000") or "4000")
                except Exception:
                    slow_ms = 4000
                if total_ms >= max(0, slow_ms):
                    logger.info(
                        "LLM cache hit",
                        extra={
                            "task": task or "",
                            "route": primary.key(),
                            "stream": bool(stream),
                            "cache_hit": True,
                            "duration_ms": total_ms,
                        },
                    )
                if stream_callback:
                    for chunk in _split_chunks(cached):
                        stream_callback(chunk)
                return self._parse_json(cached) if expect_json else cached

        def parse_attempt(a: AttemptResult) -> AttemptResult:
            if expect_json and a.ok:
                a.parsed_json = self._parse_json(a.text)
                a.valid_json = a.parsed_json is not None
            return a

        def usable(a: AttemptResult) -> bool:
            if not a.ok:
                return False
            if expect_json:
                return bool(a.valid_json)
            return True

        def finish(a: AttemptResult, *, cache_key_used: str) -> Any:
            if cache and a.ok:
                try:
                    self._cache.set(cache_key_used, a.text)
                except Exception:
                    pass
            # When `stream=True`, the streaming transport already forwarded deltas via stream_callback.
            # Avoid replaying the full text again (would duplicate UI deltas and inflate Redis payloads).
            if stream_callback and (not stream):
                for chunk in _split_chunks(a.text):
                    stream_callback(chunk)
            return a.parsed_json if expect_json else a.text

        t_total = now_perf()
        attempts: list[AttemptResult] = []

        def log_done(*, winner: Optional[AttemptResult]) -> None:
            try:
                slow_ms = int(os.getenv("DINQ_LLM_LOG_SLOW_MS", "4000") or "4000")
            except Exception:
                slow_ms = 4000
            total_ms = elapsed_ms(t_total)
            log_each = str(os.getenv("DINQ_LLM_LOG_EACH_REQUEST") or "").strip().lower() in ("1", "true", "yes", "on")
            if (not log_each) and total_ms < max(0, slow_ms) and (winner is not None and winner.ok):
                return
            logger.info(
                "LLM chat completed",
                extra={
                    "task": task or "",
                    "policy": policy,
                    "route": (winner.route.key() if winner else ""),
                    "provider": (winner.route.provider if winner else ""),
                    "model": (winner.route.model if winner else ""),
                    "stream": bool(stream),
                    "expect_json": bool(expect_json),
                    "valid_json": bool(getattr(winner, "valid_json", False)) if winner else False,
                    "cache_hit": False,
                    "duration_ms": total_ms,
                },
            )

        if policy == "single" or len(routes) <= 1:
            ck = self._hash_messages(primary.key(), messages, temperature, max_tokens, extra)
            a = parse_attempt(
                self._request_route(
                    route=primary,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    stream_callback=stream_callback,
                    extra=extra,
                    timeout_seconds=timeout_seconds,
                )
            )
            attempts.append(a)
            if a.ok:
                log_done(winner=a)
                return finish(a, cache_key_used=ck)
            log_done(winner=a)
            if a.exc:
                raise a.exc
            raise RuntimeError("LLM request failed")

        if policy == "fallback":
            last_exc: Optional[Exception] = None
            last_ok: Optional[AttemptResult] = None
            last_ok_ck: str = ""
            for r in routes:
                ck = self._hash_messages(r.key(), messages, temperature, max_tokens, extra)
                a = parse_attempt(
                    self._request_route(
                        route=r,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=stream,
                        stream_callback=stream_callback,
                        extra=extra,
                        timeout_seconds=timeout_seconds,
                    )
                )
                attempts.append(a)
                if a.exc:
                    last_exc = a.exc
                if a.ok:
                    last_ok = a
                    last_ok_ck = ck
                if usable(a):
                    log_done(winner=a)
                    return finish(a, cache_key_used=ck)
            # Nothing usable: return last ok (even if invalid JSON) or re-raise last exception.
            if last_ok is not None:
                log_done(winner=last_ok)
                return finish(last_ok, cache_key_used=last_ok_ck)
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("LLM request failed")

        # policy == "hedge"
        hedge_delay_ms = self._hedge_delay_ms(task=task)
        primary_route = routes[0]
        secondary_route = routes[1] if len(routes) > 1 else None
        tail_routes = routes[2:] if len(routes) > 2 else []

        def call_route(r: RouteSpec) -> AttemptResult:
            return parse_attempt(
                self._request_route(
                    route=r,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    stream_callback=stream_callback,
                    extra=extra,
                    timeout_seconds=timeout_seconds,
                )
            )

        futures: list[Future[AttemptResult]] = []
        futures.append(self._get_hedge_executor().submit(call_route, primary_route))

        secondary_started = False
        try:
            if secondary_route is not None:
                done, _ = wait(futures, timeout=float(hedge_delay_ms) / 1000.0)
                if done:
                    first = list(done)[0]
                    a0 = first.result()
                    attempts.append(a0)
                    if usable(a0):
                        log_done(winner=a0)
                        ck0 = self._hash_messages(a0.route.key(), messages, temperature, max_tokens, extra)
                        return finish(a0, cache_key_used=ck0)
                    # Primary finished but unusable -> start secondary immediately.
                    futures.append(self._get_hedge_executor().submit(call_route, secondary_route))
                    secondary_started = True
                else:
                    futures.append(self._get_hedge_executor().submit(call_route, secondary_route))
                    secondary_started = True

            pending: set[Future[AttemptResult]] = set(futures)
            last_exc: Optional[Exception] = None
            last_ok: Optional[AttemptResult] = None

            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for fut in done:
                    a = fut.result()
                    attempts.append(a)
                    if a.exc:
                        last_exc = a.exc
                    if a.ok:
                        last_ok = a
                    if usable(a):
                        log_done(winner=a)
                        ck_used = self._hash_messages(a.route.key(), messages, temperature, max_tokens, extra)
                        return finish(a, cache_key_used=ck_used)

            # Try remaining routes sequentially.
            for r in tail_routes:
                a = call_route(r)
                attempts.append(a)
                if a.exc:
                    last_exc = a.exc
                if a.ok:
                    last_ok = a
                if usable(a):
                    log_done(winner=a)
                    ck_used = self._hash_messages(a.route.key(), messages, temperature, max_tokens, extra)
                    return finish(a, cache_key_used=ck_used)

            if last_ok is not None:
                log_done(winner=last_ok)
                ck_ok = self._hash_messages(last_ok.route.key(), messages, temperature, max_tokens, extra)
                return finish(last_ok, cache_key_used=ck_ok)
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("LLM request failed")
        finally:
            # Best-effort: avoid leaking futures in logs; cannot reliably cancel in-flight requests.
            if secondary_started:
                pass

    def _stream_openai_compatible(
        self,
        *,
        route: RouteSpec,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        stream_callback: Optional[Callable[[str], None]],
        timeout_seconds: Optional[float] = None,
    ) -> str:
        breaker_key = self._breaker_key(route=route)
        self._breaker_check(key=breaker_key)
        response = self._get_session().post(url, headers=headers, json=payload, stream=True, timeout=timeout_seconds or 120)
        try:
            status = int(getattr(response, "status_code", 0) or 0)
            if status in (429,) or (500 <= status <= 599):
                self._breaker_record_failure(key=breaker_key)
            else:
                self._breaker_record_success(key=breaker_key)
        except Exception:
            pass
        response.raise_for_status()
        full_text = ""
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                payload = json.loads(data)
                delta = payload.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    full_text += delta
                    if stream_callback:
                        stream_callback(delta)
            except Exception:
                continue
        return full_text


_gateway: Optional[LLMGateway] = None


def get_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway


def openrouter_chat(
    *,
    messages: List[Dict[str, str]],
    task: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    expect_json: bool = False,
    stream: bool = False,
    stream_callback: Optional[Callable[[str], None]] = None,
    cache: bool = True,
    extra: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
) -> Any:
    return get_gateway().chat(
        task=task,
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        expect_json=expect_json,
        stream=stream,
        stream_callback=stream_callback,
        cache=cache,
        extra=extra,
        timeout_seconds=timeout_seconds,
    )


def _split_chunks(text: str, max_len: int = 200) -> Iterable[str]:
    if not text:
        return []
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(parts) > 1:
        return parts
    chunks = []
    buf = ""
    for ch in text:
        buf += ch
        if len(buf) >= max_len:
            chunks.append(buf)
            buf = ""
    if buf:
        chunks.append(buf)
    return chunks
