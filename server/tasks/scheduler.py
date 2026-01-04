"""
DB-backed card scheduler (rule-driven pipeline).
"""
from __future__ import annotations

from collections import OrderedDict, deque
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import logging
from typing import Any, Callable, Dict, Optional, Tuple

from server.analyze.card_specs import get_stream_spec
from server.analyze.cache_policy import (
    cache_ttl_seconds,
    compute_options_hash,
    get_pipeline_version,
    is_cacheable_subject,
)
from server.analyze.quality_gate import GateContext, validate_card_output, fallback_card_output
from server.tasks.artifact_store import ArtifactStore
from server.tasks.analysis_cache_store import AnalysisCacheStore
from server.tasks.job_store import JobStore
from server.tasks.event_store import EventStore
from server.tasks.output_schema import extract_output_parts
from server.utils.json_clean import prune_empty
from server.utils.timing import elapsed_ms, now_perf


logger = logging.getLogger(__name__)


class CardScheduler:
    def __init__(
        self,
        *,
        job_store: JobStore,
        event_store: EventStore,
        card_executor: Callable[[object], dict],
        max_workers: int = 4,
        poll_interval: float = 0.5,
        artifact_store: Optional[ArtifactStore] = None,
    ) -> None:
        self._job_store = job_store
        self._event_store = event_store
        self._artifact_store = artifact_store or ArtifactStore()
        self._analysis_cache = AnalysisCacheStore()
        self._card_executor = card_executor
        self._poll_interval = poll_interval
        self._max_workers = max(1, int(max_workers or 1))
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

        # Best-effort write-behind for final_result cache persistence.
        # This keeps user-visible completion fast (SSE job.completed) even when the DB is high RTT.
        cache_workers = max(1, min(self._read_int_env("DINQ_ANALYZE_CACHE_WRITE_MAX_WORKERS", 2), 8))
        self._cache_executor = ThreadPoolExecutor(max_workers=cache_workers, thread_name_prefix="dinq-cache-write")
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Dispatch controls (prevents one runner from hoarding too many claimed cards).
        self._pending = deque()
        self._dispatch_lock = threading.Lock()
        self._inflight = 0
        self._inflight_lock = threading.Lock()

        # Concurrency budget per group (best-effort, per-runner process).
        self._group_limits = self._parse_group_limits()
        self._group_semaphores: Dict[str, threading.BoundedSemaphore] = {}
        self._group_lock = threading.Lock()

        # Best-effort: avoid redundant cross-region job status updates. A job is marked "running" at first card start
        # within each runner process; repeated writes add DB RTT without improving correctness.
        self._running_jobs: set[str] = set()
        self._running_jobs_lock = threading.Lock()

        # Best-effort: cache immutable job metadata within the runner process to avoid repeated cross-region DB reads.
        self._job_cache_max = max(0, self._read_int_env("DINQ_JOB_CACHE_MAX", 256))
        self._job_cache: "OrderedDict[str, object]" = OrderedDict()
        self._job_cache_lock = threading.Lock()

        # Persist final business-card outputs into DB (size-capped) so /jobs snapshots remain usable even when
        # individual card payloads are large.
        self._persist_outputs_to_db = self._read_bool_env("DINQ_PERSIST_CARD_OUTPUT_TO_DB", True)
        self._persist_outputs_max_bytes = max(0, self._read_int_env("DINQ_PERSIST_CARD_OUTPUT_MAX_BYTES", 1_000_000))

    def _read_int_env(self, name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return int(default)
        try:
            return int(raw)
        except Exception:
            return int(default)

    def _read_bool_env(self, name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return bool(default)
        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    def _should_persist_card_output_to_db(self, output: Any) -> bool:
        if not self._persist_outputs_to_db:
            return False
        max_bytes = int(self._persist_outputs_max_bytes or 0)
        if max_bytes <= 0:
            return True
        try:
            raw = json.dumps(output, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except Exception:
            return False
        return len(raw) <= max_bytes

    def _max_retries_for_card(self, *, source: str, card_type: str) -> int:
        ct = str(card_type or "")
        if ct.startswith("resource."):
            return max(0, min(self._read_int_env("DINQ_ANALYZE_MAX_RETRIES_RESOURCE", 2), 10))

        ai_cards = {
            "repos",
            "role_model",
            "roast",
            "summary",
            "news",
            "level",
            "criticalReview",
            "skills",
            "career",
            "money",
        }
        if ct in ai_cards:
            return max(0, min(self._read_int_env("DINQ_ANALYZE_MAX_RETRIES_AI", 2), 10))

        # Base/data cards are usually deterministic; one retry is enough.
        return max(0, min(self._read_int_env("DINQ_ANALYZE_MAX_RETRIES_BASE", 1), 10))

    def _is_retryable_exception(self, exc: Exception) -> bool:
        # Conservative: treat most non-ValueError exceptions as retryable.
        if isinstance(exc, ValueError):
            msg = str(exc).lower()
            # Allow retries for transient-ish messages.
            if "timeout" in msg or "rate limit" in msg or "temporar" in msg:
                return True
            return False
        return True

    def _parse_group_limits(self) -> Dict[str, int]:
        """
        Parse concurrency group limits.

        Env:
          DINQ_ANALYZE_CONCURRENCY_GROUP_LIMITS="default=8,llm=2,github_api=8,crawlbase=2,apify=1"

        Semantics:
          - limit <= 0 => unlimited
          - unknown groups fall back to "default"
        """

        limits: Dict[str, int] = {
            "default": int(self._max_workers),
            # Balance: keep LLM parallelism capped by default to reduce rate-limit/cost spikes.
            "llm": int(min(4, self._max_workers)) if int(self._max_workers) > 0 else 1,
            "github_api": int(self._max_workers),
            "crawlbase": int(min(2, self._max_workers)),
            "apify": int(min(2, self._max_workers)) if int(self._max_workers) > 0 else 1,
        }

        raw = (os.getenv("DINQ_ANALYZE_CONCURRENCY_GROUP_LIMITS") or "").strip()
        if not raw:
            return limits

        for part in raw.split(","):
            item = part.strip()
            if not item or "=" not in item:
                continue
            k, v = item.split("=", 1)
            key = k.strip().lower()
            try:
                val = int(v.strip())
            except Exception:
                continue
            if not key:
                continue
            limits[key] = val

        if "default" not in limits:
            limits["default"] = int(self._max_workers)
        return limits

    def _get_job_cached(self, job_id: str):  # type: ignore[no-untyped-def]
        if not job_id or self._job_cache_max <= 0:
            return self._job_store.get_job(job_id)

        try:
            with self._job_cache_lock:
                cached = self._job_cache.get(str(job_id))
                if cached is not None:
                    self._job_cache.move_to_end(str(job_id))
                    return cached
        except Exception:
            cached = None

        job = self._job_store.get_job(job_id)
        if job is None:
            return None

        try:
            with self._job_cache_lock:
                self._job_cache[str(job_id)] = job
                self._job_cache.move_to_end(str(job_id))
                while len(self._job_cache) > int(self._job_cache_max):
                    try:
                        self._job_cache.popitem(last=False)
                    except Exception:
                        break
        except Exception:
            pass
        return job

    def _complete_card_status_and_build_streamed_output(
        self,
        *,
        card_id: int,
        internal: bool,
        output: Any,
    ) -> Dict[str, Any]:
        """
        Finalize a card (DB status update) and return the output envelope for `card.completed`.

        This implementation persists streaming deltas into `job_cards.output.stream` via `card.delta`
        events, and persists final `output.data` into `job_cards.output.data` on completion.
        """

        ended_at = datetime.utcnow()

        if internal:
            try:
                self._job_store.update_card_status(
                    card_id=int(card_id),
                    status="completed",
                    output={"data": {}, "stream": {}},
                    preserve_existing_stream=False,
                    ended_at=ended_at,
                )
            except Exception:
                pass
            return {"data": {}, "stream": {}}

        # Final output hygiene: prune empty fields by default, but preserve schema when the payload
        # explicitly requests it (e.g. unavailable/fallback payloads).
        try:
            preserve = False
            if isinstance(output, dict):
                meta = output.get("_meta")
                if isinstance(meta, dict) and meta.get("preserve_empty") is True:
                    preserve = True
                # Envelope case: {"data": {...}, "stream": {...}}
                if not preserve and "data" in output and isinstance(output.get("data"), dict):
                    meta2 = output.get("data", {}).get("_meta")
                    if isinstance(meta2, dict) and meta2.get("preserve_empty") is True:
                        preserve = True
            # CRITICAL FIX: Only prune internal cards (resource.*, full_report).
            # Business cards must preserve their schema even when empty to avoid breaking frontend.
            # CRITICAL FIX: Only prune internal cards (resource.*, full_report).
            # Business cards must preserve their schema even when empty to avoid breaking frontend.
            if not preserve and internal:
                cleaned = prune_empty(output)
                if cleaned is not None:
                    output = cleaned
        except Exception:
            pass

        merged_output = self._job_store.update_card_status(card_id=int(card_id), status="completed", output=output, ended_at=ended_at)
        return merged_output or {"data": output, "stream": {}}

    def _card_group(self, card) -> str:  # type: ignore[no-untyped-def]
        group = getattr(card, "concurrency_group", None)
        if group:
            return str(group).strip().lower() or "default"

        ct = str(getattr(card, "card_type", "") or "")
        if ct.startswith("resource."):
            return "resource"

        ai_cards = {"repos", "role_model", "roast", "summary", "news", "level", "skills", "career", "money"}
        if ct in ai_cards:
            return "llm"

        return "default"

    def _group_limit(self, group: str) -> int:
        g = (group or "default").strip().lower() or "default"
        if g in self._group_limits:
            return int(self._group_limits[g])
        return int(self._group_limits.get("default", self._max_workers))

    def _try_acquire_group_slot(self, group: str) -> Tuple[bool, Optional[threading.BoundedSemaphore]]:
        limit = self._group_limit(group)
        if limit <= 0:
            return True, None

        with self._group_lock:
            sem = self._group_semaphores.get(group)
            if sem is None:
                sem = threading.BoundedSemaphore(value=max(1, int(limit)))
                self._group_semaphores[group] = sem
        ok = sem.acquire(blocking=False)
        return bool(ok), sem

    def _inflight_get(self) -> int:
        with self._inflight_lock:
            return int(self._inflight)

    def _inflight_inc(self) -> None:
        with self._inflight_lock:
            self._inflight += 1

    def _inflight_dec(self) -> None:
        with self._inflight_lock:
            self._inflight = max(0, int(self._inflight) - 1)

    def _drain_pending(self) -> int:
        """
        Submit pending cards into the executor while respecting:
        - global max_workers
        - per-group semaphore limits

        Returns number of tasks submitted.
        """

        if not self._dispatch_lock.acquire(blocking=False):
            return 0
        try:
            submitted = 0
            if not self._pending:
                return 0

            # Try at most one full rotation; if no card can acquire a group slot, stop.
            scan_budget = len(self._pending)
            while self._pending and self._inflight_get() < self._max_workers and scan_budget > 0:
                card = self._pending.popleft()
                group = self._card_group(card)
                ok, sem = self._try_acquire_group_slot(group)
                if not ok:
                    self._pending.append(card)
                    scan_budget -= 1
                    continue

                self._inflight_inc()
                self._executor.submit(self._run_claimed_card, card, sem)
                submitted += 1
                scan_budget = len(self._pending)

            return submitted
        finally:
            self._dispatch_lock.release()

    def _run_claimed_card(self, card, sem: Optional[threading.BoundedSemaphore]) -> None:  # type: ignore[no-untyped-def]
        try:
            self._execute_card(card)
        finally:
            try:
                if sem is not None:
                    sem.release()
            except Exception:
                pass
            self._inflight_dec()
            # Kick dispatcher to avoid waiting for next poll tick.
            try:
                self._drain_pending()
            except Exception:
                pass

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="dinq-card-scheduler")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            inflight = self._inflight_get()
            # Avoid hoarding claims when we already have a large local backlog.
            if len(self._pending) >= (self._max_workers * 2):
                cards = []
            else:
                available = max(0, self._max_workers - inflight)
                claim_limit = max(1, min(10, available or 1))
                cards = self._job_store.claim_ready_cards(limit=claim_limit) if available > 0 else []
            if cards:
                self._pending.extend(cards)

            submitted = self._drain_pending()
            if not cards and not submitted:
                time.sleep(self._poll_interval)

    def _execute_card(self, card) -> None:  # type: ignore[no-untyped-def]
        job_id = card.job_id
        card_id = card.id
        internal = str(card.card_type) == "full_report" or str(card.card_type).startswith("resource.")
        ct = str(card.card_type)

        job = self._get_job_cached(job_id)
        if job is None:
            try:
                self._job_store.update_card_status(card_id=card_id, status="failed", ended_at=datetime.utcnow())
            except Exception:
                pass
            return

        source = getattr(job, "source", None)

        # Best-effort lease guard: prevent duplicate concurrent executions of the same card.
        # The (card_id, started_at) pair is written by claim_ready_cards() when the card is claimed.
        try:
            claimed_started_at = getattr(card, "started_at", None)
            if card_id is not None and claimed_started_at is not None:
                if not self._job_store.confirm_card_claim(card_id=int(card_id), started_at=claimed_started_at):
                    return
        except Exception:
            # If the guard fails unexpectedly, proceed rather than risk stalling the job.
            pass

        stream_meta = None
        try:
            spec = get_stream_spec(str(source or ""), str(card.card_type))
            if spec:
                stream_meta = {
                    "field": spec.get("field"),
                    "format": spec.get("format"),
                    "sections": spec.get("sections") or [],
                }
        except Exception:
            stream_meta = None

        should_set_running = False
        try:
            with self._running_jobs_lock:
                if str(job_id) not in self._running_jobs:
                    self._running_jobs.add(str(job_id))
                    should_set_running = True
        except Exception:
            should_set_running = True

        if should_set_running:
            try:
                self._job_store.set_job_status(job_id, "running")
            except Exception:
                # Allow retry on next card start if the DB update failed.
                try:
                    with self._running_jobs_lock:
                        self._running_jobs.discard(str(job_id))
                except Exception:
                    pass
        self._event_store.append_event(
            job_id=job_id,
            card_id=card_id,
            event_type="card.started",
            payload={
                "card": card.card_type,
                "status": "running",
                "internal": bool(internal),
                **({"stream": stream_meta} if stream_meta else {}),
            },
        )
        started_perf = now_perf()
        try:
            output = self._card_executor(card)

            stored_output = output
            if not internal:
                src = str(source or "").strip().lower()
                artifacts = {}
                try:
                    if src == "github":
                        art = self._artifact_store.get_artifact(job_id, "resource.github.data")
                        if art is not None and isinstance(art.payload, dict):
                            artifacts["resource.github.data"] = art.payload
                    elif src == "scholar":
                        art = self._artifact_store.get_artifact(job_id, "resource.scholar.page0")
                        if art is None or not isinstance(art.payload, dict):
                            art = self._artifact_store.get_artifact(job_id, "resource.scholar.base")
                        if art is not None and isinstance(art.payload, dict):
                            artifacts["resource.scholar.page0"] = art.payload
                    elif src == "linkedin":
                        art = self._artifact_store.get_artifact(job_id, "resource.linkedin.raw_profile")
                        if art is not None and isinstance(art.payload, dict):
                            artifacts["resource.linkedin.raw_profile"] = art.payload
                except Exception:
                    artifacts = {}

                ctx = GateContext(
                    source=src,
                    card_type=ct,
                    job_id=str(job_id),
                    user_id=str(getattr(job, "user_id", "") or ""),
                    full_report=None,
                    artifacts=artifacts,
                )
                decision = validate_card_output(source=src, card_type=ct, data=stored_output, ctx=ctx)
                if decision.action == "retry":
                    max_retries = self._max_retries_for_card(source=src, card_type=ct)
                    current_retry = int(getattr(card, "retry_count", 0) or 0)
                    if current_retry < max_retries:
                        next_retry = current_retry + 1
                        # Keep partial data for UX while retrying.
                        env = None
                        try:
                            env = self._job_store.update_card_status(
                                card_id=card_id,
                                status="ready",
                                output=decision.normalized,
                                retry_count=next_retry,
                                ended_at=datetime.utcnow(),
                            )
                        except Exception:
                            env = None
                        try:
                            self._event_store.append_event(
                                job_id=job_id,
                                card_id=card_id,
                                event_type="card.prefill",
                                payload={"card": ct, "payload": env or {"data": decision.normalized, "stream": {}}},
                            )
                        except Exception:
                            pass
                        try:
                            self._event_store.append_event(
                                job_id=job_id,
                                card_id=card_id,
                                event_type="card.progress",
                                payload={
                                    "card": ct,
                                    "step": "retry",
                                    "message": f"Retrying {ct} ({next_retry}/{max_retries})",
                                    "data": {
                                        "code": decision.issue.code if decision.issue else "quality_gate",
                                        "reason": decision.issue.message if decision.issue else "",
                                        "attempt_duration_ms": elapsed_ms(started_perf),
                                    },
                                },
                            )
                        except Exception:
                            pass
                        return

                    # CRITICAL FIX: Use fallback_card_output instead of marking as failed
                    # This ensures frontend always gets valid schema
                    logger.warning(
                        "Quality gate retry exhausted for %s/%s (job=%s, card=%s), using fallback",
                        src, ct, job_id, card_id
                    )
                    try:
                        fallback_payload = fallback_card_output(
                            source=src,
                            card_type=ct,
                            ctx=ctx,
                            last_decision=decision,
                            error=None,
                        )
                        stored_output = fallback_payload
                    except Exception as fb_exc:
                        logger.exception("Fallback generation failed for %s/%s: %s", src, ct, fb_exc)
                        # Ultimate fallback: empty dict with preserve_empty meta
                        stored_output = {"_meta": {"fallback": True, "preserve_empty": True, "error": "fallback_failed"}}
                    
                    # Don't return early - let the card complete with fallback payload below
                    # (execution will continue to line ~580 where card is marked completed)
                else:
                    stored_output = decision.normalized

            # Internal cards can be very large (e.g. resource payloads / full_report); avoid duplicating into
            # job_cards.output and avoid streaming the full payload over SSE.
            if internal:
                stored_output = {}
            streamed_output = self._complete_card_status_and_build_streamed_output(card_id=int(card_id), internal=bool(internal), output=stored_output)
            self._event_store.append_event(
                job_id=job_id,
                card_id=card_id,
                event_type="card.completed",
                payload={
                    "card": card.card_type,
                    "payload": streamed_output,
                    "internal": bool(internal),
                    "timing": {"duration_ms": elapsed_ms(started_perf)},
                },
            )
            # Release any pending cards whose deps are now satisfied.
            try:
                self._job_store.release_ready_cards(job_id)
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001
            src = str(source or "").strip().lower()
            max_retries = self._max_retries_for_card(source=src, card_type=ct)
            current_retry = int(getattr(card, "retry_count", 0) or 0)
            retryable = self._is_retryable_exception(exc)

            if retryable and current_retry < max_retries:
                next_retry = current_retry + 1
                self._job_store.update_card_status(card_id=card_id, status="ready", retry_count=next_retry, ended_at=datetime.utcnow())
                try:
                    self._event_store.append_event(
                        job_id=job_id,
                        card_id=card_id,
                        event_type="card.progress",
                        payload={
                            "card": ct,
                            "step": "retry",
                            "message": f"Retrying {ct} ({next_retry}/{max_retries}) after error",
                            "data": {"code": "exception", "error": str(exc)[:500]},
                        },
                    )
                except Exception:
                    pass
                return

            if not internal:
                self._job_store.update_card_status(card_id=card_id, status="failed", ended_at=datetime.utcnow())
                try:
                    self._job_store.mark_dependent_cards_skipped(job_id, ct)
                except Exception:
                    pass
                try:
                    self._event_store.append_event(
                        job_id=job_id,
                        card_id=card_id,
                        event_type="card.failed",
                        payload={
                            "card": ct,
                            "internal": False,
                            "timing": {"duration_ms": elapsed_ms(started_perf)},
                            "error": {"code": "exception", "message": str(exc), "retryable": bool(retryable)},
                        },
                    )
                except Exception:
                    pass
                try:
                    self._job_store.release_ready_cards(job_id)
                except Exception:
                    pass
                return

            # Internal cards:
            # - full_report is best-effort (skip on failure so jobs can still be "completed" for UI cards)
            # - resource.* failures are fatal (deps cannot proceed)
            if ct == "full_report":
                self._job_store.update_card_status(card_id=card_id, status="failed", ended_at=datetime.utcnow())
                try:
                    self._event_store.append_event(
                        job_id=job_id,
                        card_id=card_id,
                        event_type="card.failed",
                        payload={
                            "card": ct,
                            "internal": True,
                            "error": {"code": "full_report_failed", "message": str(exc), "retryable": False},
                            "timing": {"duration_ms": elapsed_ms(started_perf)},
                        },
                    )
                except Exception:
                    pass
                try:
                    self._job_store.mark_dependent_cards_skipped(job_id, ct)
                except Exception:
                    pass
                try:
                    self._job_store.release_ready_cards(job_id)
                except Exception:
                    pass
                return

            self._job_store.update_card_status(card_id=card_id, status="failed", ended_at=datetime.utcnow())
            # Skip cards that depend on this failure to avoid stuck jobs.
            try:
                self._job_store.mark_dependent_cards_skipped(job_id, ct)
            except Exception:
                pass
            try:
                self._event_store.append_event(
                    job_id=job_id,
                    card_id=card_id,
                    event_type="card.failed",
                    payload={
                        "card": ct,
                        "internal": bool(internal),
                        "timing": {"duration_ms": elapsed_ms(started_perf)},
                        "error": {
                            "code": "internal_error",
                            "message": str(exc),
                            "retryable": False,
                        },
                    },
                )
            except Exception:
                pass
            try:
                self._job_store.release_ready_cards(job_id)
            except Exception:
                pass
        finally:
            self._update_job_state(job_id)

    def _maybe_save_final_result_cache(self, job_id: str) -> None:
        """
        Persist a compact "final_result" cache snapshot for instant warm opens.

        This cache stores ONLY business-card outputs (internal=false), keyed by (source, subject_key,
        pipeline_version, options_hash). It intentionally excludes resource.* and full_report payloads.
        """

        job = self._get_job_cached(job_id)
        if job is None:
            return

        source = str(getattr(job, "source", "") or "").strip().lower()
        subject_key = str(getattr(job, "subject_key", "") or "").strip()
        if not source or not subject_key or not is_cacheable_subject(source=source, subject_key=subject_key):
            return

        options = getattr(job, "options", None)
        if not isinstance(options, dict):
            options = {}
        # Never write a final_result cache entry for subset jobs (cards=...).
        # Otherwise we'd overwrite the canonical (full) cache key with partial content.
        req_cards = options.get("_requested_cards")
        if isinstance(req_cards, list):
            req_cards_clean = [str(c).strip() for c in req_cards if str(c).strip()]
            if req_cards_clean:
                return
        input_payload = getattr(job, "input", None)
        if not isinstance(input_payload, dict):
            input_payload = {}

        pipeline_version = get_pipeline_version(source)
        options_hash = compute_options_hash(options)
        ttl_seconds = cache_ttl_seconds(source)

        cards = self._job_store.list_cards_for_job(str(job_id))
        by_card: Dict[str, Any] = {}
        for c in cards:
            ct = str(getattr(c, "card_type", "") or "")
            if not ct or ct == "full_report" or ct.startswith("resource."):
                continue
            if str(getattr(c, "status", "") or "") != "completed":
                # Do not cache incomplete jobs (prevents persisting transient failures as "final").
                return
            data, _stream = extract_output_parts(getattr(c, "output", None))
            if data is None:
                return
            by_card[ct] = data

        if not by_card:
            return

        subject = self._analysis_cache.get_or_create_subject(
            source=source,
            subject_key=subject_key,
            canonical_input={"content": str(input_payload.get("content") or "")},
        )
        self._analysis_cache.save_final_result(
            source=source,
            subject=subject,
            pipeline_version=pipeline_version,
            options_hash=options_hash,
            payload={"cards": by_card},
            ttl_seconds=ttl_seconds,
            meta={"cache": "write_final_result", "job_id": str(job_id), "subject_key": subject_key},
        )

    def _write_final_result_cache_async(self, job_id: str) -> None:
        try:
            fut = self._cache_executor.submit(self._maybe_save_final_result_cache, str(job_id))
        except Exception:
            return

        def _log_exc(f):  # type: ignore[no-untyped-def]
            try:
                exc = f.exception()
            except Exception:
                exc = None
            if exc is not None:
                logger.exception("final_result cache write failed (job_id=%s): %s", job_id, exc)

        try:
            fut.add_done_callback(_log_exc)
        except Exception:
            pass

    def _update_job_state(self, job_id: str) -> None:
        counts = self._job_store.count_cards_by_status(job_id)
        pending = counts.get("pending", 0) + counts.get("ready", 0) + counts.get("running", 0)
        failed = counts.get("failed", 0) + counts.get("timeout", 0)
        completed = counts.get("completed", 0)

        if pending > 0:
            return

        if failed > 0 and completed > 0:
            if self._job_store.try_finalize_job(job_id, "partial"):
                self._event_store.append_event(job_id=job_id, card_id=None, event_type="job.completed", payload={"status": "partial"})
            return

        if failed > 0 and completed == 0:
            if self._job_store.try_finalize_job(job_id, "failed"):
                # Always emit job.completed for terminal jobs so SSE clients can stop consistently.
                self._event_store.append_event(job_id=job_id, card_id=None, event_type="job.completed", payload={"status": "failed"})
                # Keep job.failed for backward compatibility / diagnostics.
                self._event_store.append_event(job_id=job_id, card_id=None, event_type="job.failed", payload={"status": "failed"})
            return

        if self._job_store.try_finalize_job(job_id, "completed"):
            self._event_store.append_event(job_id=job_id, card_id=None, event_type="job.completed", payload={"status": "completed"})
            self._write_final_result_cache_async(job_id)
