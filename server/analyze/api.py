"""Unified analysis API."""
from __future__ import annotations

import logging
import threading
import uuid
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify, Response, g
from sqlalchemy import func
from concurrent.futures import Future, ThreadPoolExecutor

from server.utils.auth import require_verified_user
from server.analyze.freeform import is_ambiguous_input, resolve_candidates
from server.analyze.cache_policy import (
    compute_options_hash,
    get_pipeline_version,
    is_cacheable_subject,
)
from server.analyze.input_resolver import SOURCE_INPUT_KEYS, normalize_input_payload
from server.analyze.subject import resolve_subject_key
from server.tasks.job_store import JobStore
from server.tasks.event_store import EventStore
from server.tasks.artifact_store import ArtifactStore
from server.tasks.analysis_cache_store import AnalysisCacheStore, build_artifact_key
from server.tasks.output_schema import ensure_output_envelope
from server.tasks.scheduler import CardScheduler
from server.analyze.pipeline import create_job_cards, PipelineExecutor
from server.analyze.card_specs import get_stream_spec
from server.analyze.quality_gate import GateContext, validate_card_output
from server.analyze import rules
from server.config.executor_mode import api_should_start_scheduler, scheduler_enabled, get_executor_mode
from server.utils.json_clean import prune_empty
from server.utils.sqlite_cache import get_sqlite_cache
from server.utils.stream_protocol import create_event, format_stream_message
from src.utils.db_utils import get_db_session
from src.models.db import AnalysisJob, AnalysisJobCard, AnalysisJobEvent


analyze_bp = Blueprint("analyze", __name__, url_prefix="/api")

logger = logging.getLogger(__name__)

_job_store = JobStore()
_event_store = EventStore()
_artifact_store = ArtifactStore()
_pipeline_executor = PipelineExecutor(_job_store, _artifact_store, _event_store)
_scheduler: Optional[CardScheduler] = None
_analysis_cache = AnalysisCacheStore()
_async_create_executor: Optional[ThreadPoolExecutor] = None
_async_create_executor_lock = threading.Lock()


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def _read_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _async_create_job_enabled() -> bool:
    return _read_bool_env("DINQ_ANALYZE_ASYNC_CREATE_JOB", False)


def _cache_hit_direct_response_enabled() -> bool:
    # Default to true when async-create is enabled, because the primary goal is "no DB writes on create".
    return _read_bool_env("DINQ_ANALYZE_CACHE_HIT_DIRECT_RESPONSE", _async_create_job_enabled())


def _get_async_create_executor() -> ThreadPoolExecutor:
    global _async_create_executor
    if _async_create_executor is not None:
        return _async_create_executor
    with _async_create_executor_lock:
        if _async_create_executor is not None:
            return _async_create_executor
        max_workers = max(1, min(_read_int_env("DINQ_ANALYZE_ASYNC_CREATE_MAX_WORKERS", 4), 32))
        _async_create_executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="dinq-analyze-async-create",
        )
        return _async_create_executor


def _log_future_exception(task_name: str, fut: Future) -> None:
    try:
        exc = fut.exception()
    except Exception:  # noqa: BLE001
        exc = None
    if exc is None:
        return
    logger.exception("%s failed: %s", task_name, exc)


def _maybe_mark_initial_ready(plan: list[dict[str, Any]]) -> None:
    # Mark cards with no deps as ready at creation time so runners can start immediately
    # without requiring an extra release_ready_cards() round trip.
    for card in plan:
        try:
            deps = card.get("depends_on")
        except Exception:
            deps = None
        if deps is None:
            deps_list: list[str] = []
        elif isinstance(deps, list):
            deps_list = [str(d).strip() for d in deps if str(d).strip()]
        else:
            deps_list = []
        if not deps_list:
            card["status"] = "ready"


def _build_cards_from_final_cache_payload(
    *,
    source: str,
    final_payload: Dict[str, Any],
    requested_cards: Optional[list[str]],
) -> Dict[str, Any]:
    """
    Convert final_result payload -> response `cards` snapshot shape:
      { "<card_type>": { "data": <payload>, "stream": {} } }
    """
    src = (source or "").strip().lower()
    cards_payload = final_payload.get("cards") if isinstance(final_payload, dict) else None
    if not isinstance(cards_payload, dict):
        return {}
    out: Dict[str, Any] = {}
    for ct in rules.normalize_cards(src, requested_cards):
        ct_str = str(ct)
        if ct_str == "full_report" or ct_str.startswith("resource."):
            continue
        raw = cards_payload.get(ct_str)
        decision = validate_card_output(
            source=src,
            card_type=ct_str,
            data=raw,
            ctx=GateContext(source=src, card_type=ct_str, full_report=None),
        )
        cleaned = prune_empty(decision.normalized)
        out[ct_str] = {"data": cleaned if cleaned is not None else decision.normalized, "stream": {}}
    return out


def _background_create_job_bundle(
    *,
    job_id: str,
    user_id: str,
    source: str,
    normalized_input: Dict[str, Any],
    requested_cards: Optional[list[str]],
    options: Dict[str, Any],
    subject_key: Optional[str],
    initial_ready: bool,
    cache_hit_payload: Optional[Dict[str, Any]],
    cache_hit_cached_at_iso: Optional[str],
    cache_hit_stale: bool,
) -> None:
    try:
        resolved_subject_key = subject_key or resolve_subject_key(source, normalized_input)
        plan = create_job_cards(source, requested_cards)
        if cache_hit_payload is not None:
            # Cache-hit completion does not need internal resource cards; skip them to reduce DB writes.
            plan = [
                c
                for c in plan
                if str((c or {}).get("card_type") or "") != "full_report"
                and not str((c or {}).get("card_type") or "").startswith("resource.")
            ]
        if initial_ready:
            _maybe_mark_initial_ready(plan)

        _job_store.create_job_bundle(
            job_id=job_id,
            user_id=user_id,
            source=source,
            input_payload=normalized_input,
            options=options or {},
            plan=plan,
            subject_key=resolved_subject_key or None,
            idempotency_key=None,
            request_hash=None,
        )

        if cache_hit_payload is not None:
            _complete_job_from_cached_final_result(
                job_id=job_id,
                source=source,
                final_payload=cache_hit_payload,
                cached_at_iso=cache_hit_cached_at_iso,
                stale=bool(cache_hit_stale),
            )

        if api_should_start_scheduler():
            init_scheduler()
    except Exception as exc:  # noqa: BLE001
        logger.exception("async create job bundle failed (job_id=%s): %s", job_id, exc)


def _should_persist_card_output_to_db(output: Any) -> bool:
    if not _read_bool_env("DINQ_PERSIST_CARD_OUTPUT_TO_DB", True):
        return False
    max_bytes = max(0, _read_int_env("DINQ_PERSIST_CARD_OUTPUT_MAX_BYTES", 1_000_000))
    if max_bytes <= 0:
        return True
    try:
        raw = json.dumps(output, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except Exception:
        return False
    return len(raw) <= int(max_bytes)


def _has_any_nonempty(data: Dict[str, Any], keys: tuple[str, ...]) -> bool:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return True
            continue
        # Non-string values: treat as present (e.g. numeric ids)
        return True
    return False


def _is_usable_final_cache_hit(
    *,
    source: str,
    final_payload: Dict[str, Any],
    requested_cards: Optional[list[str]] = None,
) -> bool:
    """
    Decide whether a cached final_result payload is usable for this request.

    final_result schema:
      { "cards": { "<card_type>": <payload> } }
    """

    src = (source or "").strip().lower()
    if not isinstance(final_payload, dict) or not final_payload:
        return False

    cards = final_payload.get("cards")
    if not isinstance(cards, dict) or not cards:
        return False

    card_types = rules.normalize_cards(src, requested_cards)
    for ct in card_types:
        ct_str = str(ct)
        if ct_str == "full_report" or ct_str.startswith("resource."):
            continue
        if ct_str not in cards:
            return False
        decision = validate_card_output(
            source=src,
            card_type=ct_str,
            data=cards.get(ct_str),
            ctx=GateContext(source=src, card_type=ct_str, full_report=None),
        )
        if decision.action != "accept":
            return False
    return True


def _try_get_l1_cached_final_result(
    *,
    source: str,
    subject_key: str,
    pipeline_version: str,
    options_hash: str,
) -> Optional[Dict[str, Any]]:
    cache = get_sqlite_cache()
    if cache is None:
        return None
    try:
        artifact_key = build_artifact_key(
            source=str(source or "").strip().lower(),
            subject_key=str(subject_key or "").strip(),
            pipeline_version=str(pipeline_version or ""),
            options_hash=str(options_hash or ""),
            kind="final_result",
        )
    except Exception:
        return None

    row = None
    try:
        row = cache.get_json(str(artifact_key))
    except Exception:
        row = None
    if row is None or not isinstance(getattr(row, "value", None), dict):
        return None

    value = row.value
    payload = value.get("payload") if isinstance(value, dict) else None
    if not isinstance(payload, dict) or not isinstance(payload.get("cards"), dict) or not payload.get("cards"):
        return None

    cached_at_iso = value.get("created_at") if isinstance(value.get("created_at"), str) else None
    now_s = int(time.time())
    expires_at_s = getattr(row, "expires_at_s", None)
    stale = bool(expires_at_s is not None and int(expires_at_s) <= now_s)

    return {
        "artifact_key": str(artifact_key),
        "payload": payload,
        "cached_at_iso": cached_at_iso,
        "stale": stale,
        "expires_at_s": expires_at_s,
    }


def init_scheduler(max_workers: Optional[int] = None) -> None:
    global _scheduler
    if not scheduler_enabled():
        return
    if _scheduler is None:
        if max_workers is None:
            max_workers = _read_int_env("DINQ_ANALYZE_SCHEDULER_MAX_WORKERS", 4)
        max_workers = max(1, min(int(max_workers), 32))
        _scheduler = CardScheduler(
            job_store=_job_store,
            event_store=_event_store,
            card_executor=lambda card: _pipeline_executor.execute_card(card, emit_deltas=True),
            max_workers=max_workers,
            artifact_store=_artifact_store,
        )
        _scheduler.start()


def create_analysis_job(
    *,
    user_id: str,
    source: str,
    input_payload: Dict[str, Any],
    requested_cards: Optional[list[str]] = None,
    options: Optional[Dict[str, Any]] = None,
    subject_key: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    request_hash: Optional[str] = None,
    initial_ready: bool = False,
) -> tuple[str, bool]:
    normalized_input = normalize_input_payload(source, input_payload or {})
    resolved_subject_key = subject_key or resolve_subject_key(source, normalized_input)
    plan = create_job_cards(source, requested_cards)
    if initial_ready:
        # Mark cards with no deps as ready at creation time so runners can start immediately
        # without requiring an extra release_ready_cards() round trip.
        for card in plan:
            try:
                deps = card.get("depends_on")
            except Exception:
                deps = None
            if deps is None:
                deps_list: list[str] = []
            elif isinstance(deps, list):
                deps_list = [str(d).strip() for d in deps if str(d).strip()]
            else:
                deps_list = []
            if not deps_list:
                card["status"] = "ready"
    job_id, created = _job_store.create_job_bundle(
        user_id=user_id,
        source=source,
        input_payload=normalized_input,
        options=options or {},
        plan=plan,
        subject_key=resolved_subject_key or None,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    return str(job_id), bool(created)


def stream_job_events(job_id: str, after_seq: int = 0):
    yield from _event_store.stream_events(job_id=job_id, after_seq=after_seq)


def run_sync_job(job_id: str, source: str, requested_cards: Optional[list[str]] = None) -> Dict[str, Any]:
    def _sync_timeout_seconds() -> int:
        # NOTE: In external runner topology, "sync" means "block until the runner finishes"
        # so this timeout needs to be reasonably large.
        return max(10, min(_read_int_env("DINQ_ANALYZE_SYNC_TIMEOUT_SECONDS", 600), 7200))

    def _collect_cards_for_response() -> tuple[str, Dict[str, Any], list[Dict[str, Any]]]:
        job = _job_store.get_job(job_id)
        status = str(getattr(job, "status", "") or "") if job is not None else "unknown"

        cards_out: Dict[str, Any] = {}
        errs: list[Dict[str, Any]] = []
        cards = _job_store.list_cards_for_job(job_id)
        for c in cards:
            ct = str(getattr(c, "card_type", "") or "")
            if not ct or ct == "full_report" or ct.startswith("resource."):
                continue
            if requested_cards and ct not in requested_cards:
                continue
            card_id = getattr(c, "id", None)
            if _event_store.redis_enabled() and card_id is not None:
                env = _event_store.get_card_output(card_id=int(card_id))
            else:
                env = ensure_output_envelope(getattr(c, "output", None))
            cards_out[ct] = env

            st = str(getattr(c, "status", "") or "")
            if st in ("failed", "timeout"):
                errs.append({"card": ct, "status": st})
        return status, cards_out, errs

    # In external topology, the API process must NOT execute cards (runner does that).
    # "sync" here means: wait for terminal, then return a snapshot of all cards.
    if get_executor_mode() == "external":
        try:
            _job_store.release_ready_cards(job_id)
        except Exception:
            pass

        terminal = {"completed", "partial", "failed", "cancelled"}
        deadline = time.monotonic() + float(_sync_timeout_seconds())
        while time.monotonic() < deadline:
            job = _job_store.get_job(job_id)
            if job is None:
                return {"success": False, "job_id": job_id, "status": "not_found", "cards": {}, "errors": [{"error": "job not found"}]}, 404
            if str(getattr(job, "status", "") or "") in terminal:
                break
            time.sleep(0.15)

        status, cards_out, errs = _collect_cards_for_response()
        if status not in terminal:
            # Timed out waiting: return partial snapshot + let the client continue via SSE.
            return {
                "success": True,
                "job_id": job_id,
                "status": status or "running",
                "cards": cards_out,
                "errors": errs,
                "timeout": True,
                "stream_url": f"/api/analyze/jobs/{job_id}/stream?after=0",
            }, 200
        return {"success": True, "job_id": job_id, "status": status, "cards": cards_out, "errors": errs}, 200

    results: Dict[str, Any] = {}
    errors: list[Dict[str, Any]] = []

    def _max_retries_for_card(card_type: str) -> int:
        ct = str(card_type or "")
        if ct.startswith("resource."):
            return max(0, min(_read_int_env("DINQ_ANALYZE_MAX_RETRIES_RESOURCE", 2), 10))
        if ct in {"repos", "role_model", "roast", "summary", "news", "level", "criticalReview", "skills", "career", "money"}:
            return max(0, min(_read_int_env("DINQ_ANALYZE_MAX_RETRIES_AI", 2), 10))
        return max(0, min(_read_int_env("DINQ_ANALYZE_MAX_RETRIES_BASE", 1), 10))

    def _is_retryable_exception(exc: Exception) -> bool:
        if isinstance(exc, ValueError):
            msg = str(exc).lower()
            if "timeout" in msg or "rate limit" in msg or "temporar" in msg:
                return True
            return False
        return True

    # Cards are created in "pending" state; promote runnable cards to "ready" before executing.
    try:
        _job_store.release_ready_cards(job_id)
    except Exception:
        pass

    # Execute cards in dependency order (same semantics as the background scheduler).
    terminal = {"completed", "partial", "failed", "cancelled"}
    deadline = time.monotonic() + float(_sync_timeout_seconds())
    while time.monotonic() < deadline:
        job = _job_store.get_job(job_id)
        if job is not None and str(getattr(job, "status", "") or "") in terminal:
            break
        cards = _job_store.list_cards_for_job(job_id)
        ready = [c for c in cards if c.status == "ready"]
        pending = [c for c in cards if c.status in ("pending", "running")]
        if not ready:
            if not pending:
                break
            # No runnable cards but still pending => release deps and wait.
            try:
                _job_store.release_ready_cards(job_id)
            except Exception:
                pass
            time.sleep(0.05)
            continue

        for c in ready:
            if requested_cards and c.card_type not in requested_cards and c.card_type not in ("full_report",) and not str(c.card_type).startswith("resource."):
                # Keep deps for correctness, but skip optional non-requested UI cards.
                _job_store.update_card_status(card_id=c.id, status="skipped")
                continue

            try:
                ct = str(c.card_type)
                internal = ct == "full_report" or ct.startswith("resource.")
                max_retries = _max_retries_for_card(ct)
                retry_count = int(getattr(c, "retry_count", 0) or 0)

                artifacts: Dict[str, Any] = {}
                try:
                    if source == "github":
                        art = _artifact_store.get_artifact(job_id, "resource.github.data")
                        if art is not None and isinstance(art.payload, dict):
                            artifacts["resource.github.data"] = art.payload
                    elif source == "scholar":
                        art = _artifact_store.get_artifact(job_id, "resource.scholar.page0")
                        if art is None or not isinstance(art.payload, dict):
                            art = _artifact_store.get_artifact(job_id, "resource.scholar.base")
                        if art is not None and isinstance(art.payload, dict):
                            artifacts["resource.scholar.page0"] = art.payload
                    elif source == "linkedin":
                        art = _artifact_store.get_artifact(job_id, "resource.linkedin.raw_profile")
                        if art is not None and isinstance(art.payload, dict):
                            artifacts["resource.linkedin.raw_profile"] = art.payload
                except Exception:
                    artifacts = {}

                _job_store.update_card_status(card_id=c.id, status="running")
                _event_store.append_event(job_id=job_id, card_id=c.id, event_type="card.started", payload={"card": ct, "status": "running"})

                final_payload: Any = None
                last_decision = None
                last_error: Optional[Exception] = None

                while True:
                    try:
                        raw = _pipeline_executor.execute_card(c, emit_deltas=False)
                        last_error = None
                        if internal:
                            final_payload = {} if internal else raw  # pragma: no cover
                            break

                        ctx = GateContext(source=str(source), card_type=ct, job_id=job_id, full_report=None, artifacts=artifacts)
                        decision = validate_card_output(source=str(source), card_type=ct, data=raw, ctx=ctx)
                        last_decision = decision
                        if decision.action == "accept":
                            final_payload = decision.normalized
                            break

                        if retry_count < max_retries:
                            retry_count += 1
                            _event_store.append_event(
                                job_id=job_id,
                                card_id=c.id,
                                event_type="card.progress",
                                payload={
                                    "card": ct,
                                    "step": "retry",
                                    "message": f"Retrying {ct} ({retry_count}/{max_retries})",
                                    "data": {"code": decision.issue.code if decision.issue else "quality_gate"},
                                },
                            )
                            continue

                        raise RuntimeError(
                            f"quality_gate_failed:{decision.issue.code if decision.issue else 'quality_gate'}"
                        )
                    except Exception as exc:  # noqa: BLE001
                        last_error = exc
                        if _is_retryable_exception(exc) and retry_count < max_retries:
                            retry_count += 1
                            _event_store.append_event(
                                job_id=job_id,
                                card_id=c.id,
                                event_type="card.progress",
                                payload={
                                    "card": ct,
                                    "step": "retry",
                                    "message": f"Retrying {ct} ({retry_count}/{max_retries}) after error",
                                    "data": {"code": "exception", "error": str(exc)[:200]},
                                },
                            )
                            continue
                        raise

                if internal:
                    if ct == "full_report":
                        _job_store.update_card_status(card_id=c.id, status="skipped", retry_count=retry_count)
                        continue
                    # resource.* and other internal payloads are not duplicated into job_cards.output
                    merged = _job_store.update_card_status(card_id=c.id, status="completed", output={}, retry_count=retry_count)
                    env = merged or {"data": {}, "stream": {}}
                    _event_store.append_event(job_id=job_id, card_id=c.id, event_type="card.completed", payload={"card": ct, "payload": env, "internal": True})
                    continue

                if _event_store.redis_enabled():
                    try:
                        existing = _event_store.get_card_output(card_id=int(c.id))
                        stream = existing.get("stream") if isinstance(existing, dict) else {}
                    except Exception:
                        stream = {}
                    if _should_persist_card_output_to_db(final_payload):
                        stored = final_payload if isinstance(final_payload, dict) else {"data": final_payload, "stream": {}}
                        _job_store.update_card_status(
                            card_id=c.id,
                            status="completed",
                            output=stored,
                            preserve_existing_stream=False,
                            retry_count=retry_count,
                        )
                    else:
                        _job_store.update_card_status(card_id=c.id, status="completed", output=None, retry_count=retry_count)
                    env = {"data": final_payload, "stream": stream or {}}
                else:
                    merged = _job_store.update_card_status(card_id=c.id, status="completed", output=final_payload, retry_count=retry_count)
                    env = merged or {"data": final_payload, "stream": {}}
                _event_store.append_event(job_id=job_id, card_id=c.id, event_type="card.completed", payload={"card": ct, "payload": env, "internal": False})
                results[ct] = env
            except Exception as exc:  # noqa: BLE001
                _job_store.update_card_status(card_id=c.id, status="failed")
                _job_store.mark_dependent_cards_skipped(job_id, str(c.card_type))
                _event_store.append_event(
                    job_id=job_id,
                    card_id=c.id,
                    event_type="card.failed",
                    payload={"card": c.card_type, "error": {"code": "internal_error", "message": str(exc), "retryable": False}},
                )
                errors.append({"card": c.card_type, "error": str(exc)})
            finally:
                try:
                    _job_store.release_ready_cards(job_id)
                except Exception:
                    pass

    # Finalize the job only when there are no pending/ready/running cards left.
    try:
        counts = _job_store.count_cards_by_status(job_id)
        pending_n = counts.get("pending", 0) + counts.get("ready", 0) + counts.get("running", 0)
        failed_n = counts.get("failed", 0) + counts.get("timeout", 0)
        completed_n = counts.get("completed", 0)
        if pending_n <= 0:
            if failed_n > 0 and completed_n > 0:
                status = "partial"
            elif failed_n > 0 and completed_n <= 0:
                status = "failed"
            else:
                status = "completed"
            event_type = "job.failed" if status == "failed" else "job.completed"
            if _job_store.try_finalize_job(job_id, status):
                _event_store.append_event(job_id=job_id, card_id=None, event_type=event_type, payload={"status": status})
    except Exception:
        pass

    status, cards_out, errs = _collect_cards_for_response()
    merged_errors = errors + [e for e in errs if e not in errors]
    if status not in terminal and time.monotonic() >= deadline:
        return {"success": True, "job_id": job_id, "status": status or "running", "cards": cards_out, "errors": merged_errors, "timeout": True}, 200

    return {"success": True, "job_id": job_id, "status": status, "cards": cards_out, "errors": merged_errors}, 200


def _complete_job_from_cached_final_result(
    *,
    job_id: str,
    source: str,
    final_payload: Dict[str, Any],
    cached_at_iso: Optional[str],
    stale: bool = False,
) -> None:
    cache_meta = {"hit": True, "stale": bool(stale), "as_of": cached_at_iso}
    use_redis = _event_store.redis_enabled()
    realtime_events: list[tuple[int, str, Dict[str, Any]]] = []

    cards_payload = final_payload.get("cards") if isinstance(final_payload, dict) else None
    if not isinstance(cards_payload, dict) or not cards_payload:
        return

    # IMPORTANT: this path is performance-sensitive. A cache-hit should complete in ~<1s.
    # Avoid per-card DB transactions by batching all updates/events in a single commit.
    with get_db_session() as session:
        job = None
        try:
            job = session.query(AnalysisJob).filter(AnalysisJob.id == job_id).with_for_update().first()
        except Exception:  # noqa: BLE001
            job = session.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job is None:
            return

        terminal_states = {"completed", "partial", "failed", "cancelled"}
        if str(getattr(job, "status", "") or "") in terminal_states:
            # Strict requirement: do not emit job.completed more than once.
            return

        q = (
            session.query(AnalysisJobCard)
            .filter(AnalysisJobCard.job_id == job_id)
            .order_by(AnalysisJobCard.id.asc())
        )
        try:
            q = q.with_for_update()
        except Exception:  # noqa: BLE001
            pass
        cards = q.all()

        expected_types: list[str] = []
        for c in cards:
            ct = str(c.card_type)
            if ct.startswith("resource.") or ct == "full_report":
                continue
            expected_types.append(ct)
        missing = [ct for ct in expected_types if ct not in cards_payload]
        if missing:
            # Defensive: a usable cache-hit should always contain all business cards.
            return

        next_seq = 0
        events: list[AnalysisJobEvent] = []
        if not use_redis:
            last_seq = 0
            try:
                last_seq = int(getattr(job, "last_seq", 0) or 0) if job is not None else 0
            except Exception:
                last_seq = 0
            if last_seq <= 0:
                max_seq = (
                    session.query(func.max(AnalysisJobEvent.seq))
                    .filter(AnalysisJobEvent.job_id == job_id)
                    .scalar()
                )
                last_seq = int(max_seq or 0)
            next_seq = int(last_seq) + 1

        src = str(source or "").strip().lower()
        for c in cards:
            ct = str(c.card_type)

            if ct.startswith("resource."):
                c.status = "skipped"
                continue

            if ct == "full_report":
                # Backward-compat: older jobs may include full_report; complete it as internal empty.
                c.status = "completed"
                payload = {"card": ct, "payload": {"data": {}, "stream": {}}, "cache": cache_meta, "internal": True}
                if not use_redis:
                    c.output = {"data": {}, "stream": {}}
                    events.append(
                        AnalysisJobEvent(
                            job_id=job_id,
                            card_id=c.id,
                            seq=next_seq,
                            event_type="card.completed",
                            payload=payload,
                        )
                    )
                    next_seq += 1
                realtime_events.append((int(c.id), "card.completed", payload))
                continue

            decision = validate_card_output(
                source=src,
                card_type=ct,
                data=cards_payload.get(ct),
                ctx=GateContext(source=src, card_type=ct, full_report=None),
            )
            payload = decision.normalized
            c.status = "completed"
            ev_payload = {"card": ct, "payload": {"data": payload, "stream": {}}, "cache": cache_meta, "internal": False}
            if not use_redis:
                c.output = {"data": payload, "stream": {}}
                events.append(
                    AnalysisJobEvent(
                        job_id=job_id,
                        card_id=c.id,
                        seq=next_seq,
                        event_type="card.completed",
                        payload=ev_payload,
                    )
                )
                next_seq += 1
            realtime_events.append((int(c.id), "card.completed", ev_payload))

        job.status = "completed"
        job.updated_at = datetime.utcnow()
        if not use_redis:
            try:
                job.last_seq = int(next_seq)
            except Exception:
                pass
            events.append(
                AnalysisJobEvent(
                    job_id=job_id,
                    card_id=None,
                    seq=next_seq,
                    event_type="job.completed",
                    payload={"status": "completed", "cache": cache_meta},
                )
            )
            session.add_all(events)

    if use_redis:
        for cid, et, p in realtime_events:
            try:
                _event_store.append_event(job_id=job_id, card_id=int(cid), event_type=str(et), payload=p)
            except Exception:
                pass
        try:
            _event_store.append_event(job_id=job_id, card_id=None, event_type="job.completed", payload={"status": "completed", "cache": cache_meta})
        except Exception:
            pass


def _read_idempotency_key() -> str:
    return (
        (request.headers.get("Idempotency-Key") or "").strip()
        or (request.headers.get("X-Idempotency-Key") or "").strip()
    )


def _hash_create_payload(
    *,
    source: str,
    input_payload: Dict[str, Any],
    requested_cards: Optional[list[str]],
    options: Dict[str, Any],
) -> str:
    cards = None
    if requested_cards:
        cards = sorted({str(c).strip() for c in requested_cards if str(c).strip()})
    raw = json.dumps(
        {
            "source": str(source),
            "input": input_payload or {},
            "cards": cards,
            "options": options or {},
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@analyze_bp.route("/analyze", methods=["POST", "OPTIONS"])
@require_verified_user
def analyze():
    if request.method == "OPTIONS":
        return Response(status=200)

    data = request.get_json() or {}
    source = (data.get("source") or "").strip().lower()
    mode = (data.get("mode") or "async").strip().lower()
    input_payload = data.get("input") or {}
    cards_raw = data.get("cards", None)
    if cards_raw is not None and not isinstance(cards_raw, list):
        return jsonify({"success": False, "error": "invalid cards: must be an array of strings"}), 400
    requested_cards = cards_raw or None
    options_raw = data.get("options") or {}

    if not source:
        return jsonify({"success": False, "error": "missing source"}), 400
    if not isinstance(input_payload, dict):
        return jsonify({"success": False, "error": "invalid input: must be an object"}), 400
    if options_raw is not None and not isinstance(options_raw, dict):
        return jsonify({"success": False, "error": "invalid options: must be an object"}), 400

    # Keep a copy so we can inject internal metadata without mutating the client payload.
    options = dict(options_raw or {})
    if requested_cards:
        cleaned = [str(c).strip() for c in requested_cards if str(c).strip()]
        if cleaned:
            options["_requested_cards"] = cleaned

    normalized_input = normalize_input_payload(source, input_payload)

    expected_keys = SOURCE_INPUT_KEYS.get(source)
    if expected_keys and not _has_any_nonempty(normalized_input, expected_keys):
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"missing input for source={source} (prefer input.content)",
                    "details": {"expected_any_of": list(expected_keys)},
                }
            ),
            400,
        )

    user_id = getattr(g, "user_id", None) or "anonymous"

    content = str((normalized_input or {}).get("content") or "").strip()

    # Fast-fail on obviously invalid platform URLs that couldn't be normalized.
    if source == "github" and "github.com" in content:
        return jsonify({"success": False, "error": "invalid github input; provide a login or profile URL"}), 400
    if source == "scholar" and ("scholar.google" in content and "citations" in content):
        return jsonify({"success": False, "error": "invalid scholar input; provide scholar id or profile URL with ?user="}), 400
    if source == "twitter" and ("twitter.com" in content or "x.com" in content):
        return jsonify({"success": False, "error": "invalid twitter input; provide a username or profile URL"}), 400
    if source == "huggingface" and "huggingface.co" in content:
        return jsonify({"success": False, "error": "invalid huggingface input; provide a username or profile URL"}), 400

    # Canonicalize ambiguous inputs for cache safety (scholar/github/linkedin).
    # - If we can resolve exactly 1 stable candidate => auto-canonicalize and proceed.
    # - If we have multiple/no candidates => ask for confirmation (no job created).
    allow_ambiguous = bool((options_raw or {}).get("allow_ambiguous"))
    auto_canonicalize = (source in ("scholar", "github", "linkedin")) and (not allow_ambiguous)
    freeform_enabled = bool((options_raw or {}).get("freeform"))
    if (auto_canonicalize or freeform_enabled) and is_ambiguous_input(source, content):
        candidates = resolve_candidates(source, content, user_id=user_id)
        if len(candidates) == 1:
            chosen = (candidates[0] or {}).get("input") or {}
            chosen_content = str((chosen or {}).get("content") or "").strip()
            if chosen_content:
                normalized_input["content"] = chosen_content
                content = chosen_content
        else:
            return (
                jsonify(
                    {
                        "success": True,
                        "needs_confirmation": True,
                        "source": source,
                        "input": {"content": content},
                        "candidates": candidates,
                        "message": (
                            "Please choose a candidate and retry with input.content set to the selected stable id/login/url."
                            if candidates
                            else "Input is not a stable id/url/login and no candidates were found; please provide an explicit URL/ID."
                        ),
                    }
                ),
                200,
            )

    subject_key = resolve_subject_key(source, normalized_input)

    # Cache pre-check (before creating a job):
    # - Enables "instant return" when we already have a cached final_result for a stable subject id.
    # - When cache miss, we can create initial runnable cards as READY to avoid an extra DB round trip.
    options_hash = compute_options_hash(options or {})
    pipeline_version = get_pipeline_version()
    force_refresh = bool((options or {}).get("force_refresh"))
    cache_hit_payload: Optional[Dict[str, Any]] = None
    cache_hit_source: Optional[str] = None
    cache_hit_stale = False
    cache_hit_cached_at_iso: Optional[str] = None

    if subject_key and is_cacheable_subject(source=source, subject_key=subject_key) and not force_refresh:
        try:
            l1_final = _try_get_l1_cached_final_result(
                source=source,
                subject_key=subject_key,
                pipeline_version=pipeline_version,
                options_hash=options_hash,
            )
            if l1_final and isinstance(l1_final.get("payload"), dict) and l1_final.get("payload"):
                payload = l1_final["payload"]
                if _is_usable_final_cache_hit(source=source, final_payload=payload, requested_cards=requested_cards):
                    cache_hit_payload = payload
                    cache_hit_source = "l1"
                    cache_hit_stale = bool(l1_final.get("stale"))
                    cache_hit_cached_at_iso = l1_final.get("cached_at_iso") or datetime.utcnow().isoformat()
        except Exception:
            pass

        if cache_hit_payload is None:
            try:
                cached = _analysis_cache.get_cached_final_result(
                    source=source,
                    subject_key=subject_key,
                    pipeline_version=pipeline_version,
                    options_hash=options_hash,
                )
                if cached and isinstance(cached.get("payload"), dict) and cached.get("payload"):
                    payload = cached.get("payload") or {}
                    if _is_usable_final_cache_hit(source=source, final_payload=payload, requested_cards=requested_cards):
                        created_at = cached.get("created_at") if isinstance(cached.get("created_at"), datetime) else None
                        cache_hit_payload = payload
                        cache_hit_source = "db"
                        cache_hit_stale = bool(cached.get("stale"))
                        cache_hit_cached_at_iso = (created_at or datetime.utcnow()).isoformat()
            except Exception:
                pass

    idempotency_key = _read_idempotency_key()
    if idempotency_key and len(idempotency_key) > 128:
        return jsonify({"success": False, "error": "Idempotency-Key too long (max 128 chars)"}), 400
    request_hash = _hash_create_payload(
        source=source,
        input_payload=normalized_input,
        requested_cards=requested_cards,
        options=options_raw or {},
    ) if idempotency_key else None

    # Cache-hit direct response (no DB writes): return cards immediately.
    # This keeps create() fast even when Postgres is high RTT, and avoids the slow "complete job from cache"
    # DB write path.
    if mode == "async" and cache_hit_payload is not None and _cache_hit_direct_response_enabled():
        cards_out = _build_cards_from_final_cache_payload(
            source=source,
            final_payload=cache_hit_payload,
            requested_cards=requested_cards,
        )
        return jsonify(
            {
                "success": True,
                "job_id": uuid.uuid4().hex,
                "status": "completed",
                "cache_hit": True,
                "cache_stale": bool(cache_hit_stale),
                "cache_source": cache_hit_source,
                "ephemeral_job": True,
                "cards": cards_out,
                "errors": [],
                "idempotent_replay": False,
            }
        )

    # Async-create mode: return a job_id immediately and create the DB job bundle in background.
    if mode == "async" and _async_create_job_enabled() and not idempotency_key:
        job_id = uuid.uuid4().hex
        fut = _get_async_create_executor().submit(
            _background_create_job_bundle,
            job_id=job_id,
            user_id=user_id,
            source=source,
            normalized_input=dict(normalized_input or {}),
            requested_cards=list(requested_cards) if requested_cards else None,
            options=dict(options or {}),
            subject_key=subject_key or None,
            initial_ready=(cache_hit_payload is None),
            cache_hit_payload=dict(cache_hit_payload) if isinstance(cache_hit_payload, dict) else None,
            cache_hit_cached_at_iso=cache_hit_cached_at_iso,
            cache_hit_stale=bool(cache_hit_stale),
        )
        fut.add_done_callback(lambda f: _log_future_exception("async_create_job_bundle", f))

        if api_should_start_scheduler():
            init_scheduler()

        return jsonify(
            {
                "success": True,
                "job_id": job_id,
                "status": "queued",
                "cache_hit": bool(cache_hit_payload is not None),
                "cache_stale": bool(cache_hit_stale) if cache_hit_payload is not None else False,
                "cache_source": cache_hit_source if cache_hit_payload is not None else None,
                "async_create": True,
                "idempotent_replay": False,
            }
        )

    try:
        job_id, created = create_analysis_job(
            user_id=user_id,
            source=source,
            input_payload=normalized_input,
            requested_cards=requested_cards,
            options=options,
            subject_key=subject_key or None,
            idempotency_key=idempotency_key or None,
            request_hash=request_hash,
            initial_ready=(cache_hit_payload is None),
        )
    except ValueError as exc:
        if str(exc) == "idempotency_key_conflict":
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Idempotency-Key reused with a different request payload",
                        "details": {"idempotency_key": idempotency_key},
                    }
                ),
                409,
            )
        if str(exc).startswith("missing request_hash"):
            return jsonify({"success": False, "error": "invalid idempotency request"}), 400
        raise

    # When Redis realtime is enabled, ensure a best-effort `job.started` event is present in Redis so SSE clients
    # can start immediately without depending on cross-region DB job_events.
    if created and _event_store.redis_enabled():
        try:
            _event_store.bootstrap_job_started_realtime(job_id=job_id, source=source)
        except Exception:
            pass

    if mode == "sync":
        if created and cache_hit_payload is not None:
            _complete_job_from_cached_final_result(
                job_id=job_id,
                source=source,
                final_payload=cache_hit_payload,
                cached_at_iso=cache_hit_cached_at_iso,
                stale=bool(cache_hit_stale),
            )
        payload, status = run_sync_job(job_id, source, requested_cards)
        return jsonify(payload), status

    # async mode (default): client should use GET .../stream for SSE.
    if created and cache_hit_payload is not None:
        _complete_job_from_cached_final_result(
            job_id=job_id,
            source=source,
            final_payload=cache_hit_payload,
            cached_at_iso=cache_hit_cached_at_iso,
            stale=bool(cache_hit_stale),
        )
        return jsonify(
            {
                "success": True,
                "job_id": job_id,
                "status": "completed",
                "cache_hit": True,
                "cache_stale": bool(cache_hit_stale),
                "cache_source": cache_hit_source,
                "idempotent_replay": False,
            }
        )

    if api_should_start_scheduler():
        init_scheduler()
    # Backward compat: idempotency replays may point at older jobs whose initial cards were created as pending.
    if not created:
        try:
            _job_store.release_ready_cards(job_id)
        except Exception:
            pass
    job = _job_store.get_job(job_id) if (not created) else None
    return jsonify(
        {
            "success": True,
            "job_id": job_id,
            "status": (getattr(job, "status", None) if job is not None else "queued") or "queued",
            "idempotent_replay": (not created) if idempotency_key else False,
        }
    )


@analyze_bp.route("/analyze/jobs/<job_id>", methods=["GET", "OPTIONS"])
@require_verified_user
def get_job(job_id: str):
    if request.method == "OPTIONS":
        return Response(status=200)

    use_redis = _event_store.redis_enabled()
    rec = _job_store.get_job_with_cards(job_id, include_output=(not use_redis))
    if rec is None:
        return jsonify({"success": False, "error": "job not found"}), 404

    job = rec["job"]
    current_user_id = getattr(g, "user_id", None)
    if current_user_id and getattr(job, "user_id", None) != current_user_id:
        return jsonify({"success": False, "error": "job not found"}), 404
    cards = rec["cards"]
    # Avoid an extra DB round trip: jobs.last_seq is maintained by EventStore.append_event.
    if _event_store.redis_enabled():
        last_seq = _event_store.get_last_seq(job_id)
    else:
        try:
            last_seq = int(getattr(job, "last_seq", 0) or 0)
        except Exception:
            last_seq = 0
        if last_seq <= 0:
            last_seq = _event_store.get_last_seq(job_id)

    source = str(getattr(job, "source", "") or "").strip().lower()

    # In Redis mode, fetch all non-internal card outputs in one pipelined call to reduce RTT/CPU.
    outputs_by_id: Dict[int, Dict[str, Any]] = {}
    db_fallback_by_id: Dict[int, Dict[str, Any]] = {}
    if use_redis:
        non_internal_ids: list[int] = []
        for c in cards:
            ct = str(getattr(c, "card_type", "") or "")
            if ct == "full_report" or ct.startswith("resource."):
                continue
            cid = getattr(c, "id", None)
            if cid is None:
                continue
            try:
                non_internal_ids.append(int(cid))
            except Exception:
                continue
        try:
            outputs_by_id = _event_store.get_card_outputs(card_ids=non_internal_ids)
        except Exception:
            outputs_by_id = {}

        # Redis keys may be evicted/expired while Redis is still reachable. For completed business cards,
        # fall back to DB-persisted final outputs (when available) to avoid empty snapshots.
        missing: list[int] = []
        for c in cards:
            ct = str(getattr(c, "card_type", "") or "")
            if ct == "full_report" or ct.startswith("resource."):
                continue
            if str(getattr(c, "status", "") or "") not in ("completed", "failed", "timeout"):
                continue
            cid = getattr(c, "id", None)
            if cid is None:
                continue
            try:
                cid_int = int(cid)
            except Exception:
                continue
            env = outputs_by_id.get(cid_int) if isinstance(outputs_by_id, dict) else None
            if not isinstance(env, dict) or (env.get("data") is None and not env.get("stream")):
                missing.append(cid_int)
        if missing:
            try:
                db_fallback_by_id = _job_store.get_card_outputs(missing)
            except Exception:
                db_fallback_by_id = {}

    def _card_snapshot(c: AnalysisJobCard) -> Dict[str, Any]:
        ct = str(getattr(c, "card_type", "") or "")
        internal = ct == "full_report" or ct.startswith("resource.")
        spec = get_stream_spec(source, ct)
        stream_spec = None
        if spec:
            stream_spec = {
                "field": spec.get("field"),
                "format": spec.get("format"),
                "sections": spec.get("sections") or [],
            }

        output_env: Dict[str, Any]
        if use_redis:
            if internal:
                output_env = {"data": None, "stream": {}}
            else:
                try:
                    cid_int = int(getattr(c, "id"))
                except Exception:
                    cid_int = 0
                env = outputs_by_id.get(cid_int) if cid_int and isinstance(outputs_by_id, dict) else None
                if not isinstance(env, dict) or (env.get("data") is None and not env.get("stream")):
                    fallback = db_fallback_by_id.get(cid_int) if cid_int and isinstance(db_fallback_by_id, dict) else None
                    if isinstance(fallback, dict):
                        env = fallback
                output_env = env if isinstance(env, dict) else {"data": None, "stream": {}}
        else:
            output_env = ensure_output_envelope(getattr(c, "output", None))
        return {
            "status": c.status,
            "internal": bool(internal),
            "output": output_env,
            **({"stream_spec": stream_spec} if stream_spec else {}),
        }
    return jsonify(
        {
            "success": True,
            "job": {
                "job_id": job.id,
                "source": job.source,
                "status": job.status,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
                "last_seq": last_seq,
                "next_after": last_seq,
                "cards": {
                    c.card_type: _card_snapshot(c)
                    for c in cards
                },
            },
        }
    )


@analyze_bp.route("/analyze/jobs/<job_id>/stream", methods=["GET", "OPTIONS"])
@require_verified_user
def stream_job(job_id: str):
    if request.method == "OPTIONS":
        return Response(status=200)

    current_user_id = getattr(g, "user_id", None)
    rec = _job_store.get_job(job_id)
    if rec is None and not _async_create_job_enabled():
        return jsonify({"success": False, "error": "job not found"}), 404
    if rec is not None and current_user_id and getattr(rec, "user_id", None) != current_user_id:
        return jsonify({"success": False, "error": "job not found"}), 404

    after = request.args.get("after", "0")
    try:
        after_seq = int(after or "0")
    except ValueError:
        after_seq = 0

    def generate():
        nonlocal rec

        # Async-create may return a job_id before the DB bundle exists. Wait briefly so the client can
        # open SSE immediately without retrying.
        if rec is None and _async_create_job_enabled():
            wait_s = float(os.getenv("DINQ_ANALYZE_STREAM_WAIT_FOR_JOB_SECONDS", "10") or "10")
            poll_s = float(os.getenv("DINQ_ANALYZE_STREAM_WAIT_FOR_JOB_POLL_SECONDS", "0.15") or "0.15")
            poll_s = max(0.05, min(poll_s, 2.0))
            deadline = time.monotonic() + max(0.0, wait_s)
            last_ping = 0.0

            while rec is None and time.monotonic() < deadline:
                now = time.monotonic()
                if (now - last_ping) >= 1.0:
                    yield format_stream_message(
                        create_event(
                            source="analysis",
                            event_type="ping",
                            message="",
                            step="wait_job",
                            legacy_type="ping",
                            payload={"job_id": job_id, "seq": 0},
                        )
                    )
                    last_ping = now
                time.sleep(poll_s)
                rec = _job_store.get_job(job_id)

        if rec is None:
            yield format_stream_message(
                create_event(
                    source="analysis",
                    event_type="job.not_found",
                    message="job not found",
                    payload={"job_id": job_id, "seq": 0},
                )
            )
            return

        if current_user_id and getattr(rec, "user_id", None) != current_user_id:
            yield format_stream_message(
                create_event(
                    source="analysis",
                    event_type="job.not_found",
                    message="job not found",
                    payload={"job_id": job_id, "seq": 0},
                )
            )
            return

        # Ensure scheduler is running for non-terminal jobs (service restarts, etc.).
        if api_should_start_scheduler() and getattr(rec, "status", "") not in ("completed", "partial", "failed", "cancelled"):
            init_scheduler()
        yield from _event_store.stream_events(job_id=job_id, after_seq=after_seq, stop_when_done=True, job_store=_job_store)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
