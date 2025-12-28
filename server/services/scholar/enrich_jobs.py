"""
Scholar background jobs:

- cache_repair: 缓存命中但缺字段时，后台补齐缺失 enrich 字段并写回 DB + 覆盖 reports JSON。
- full_refresh: 冷启动先简化秒出，后台跑完整分析并写回 DB + 覆盖 reports JSON。
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from server.api.scholar.report_generator import save_scholar_report
from server.config.api_keys import API_KEYS
from server.services.scholar.cache_validator import validate_and_complete_cache
from server.services.scholar.completeness import compute_scholar_completeness
from server.services.scholar.scholar_service import ScholarService, run_scholar_analysis
from server.utils.job_manager import JobContext, JobManager


def detect_missing_enrich(report: Optional[Dict[str, Any]]) -> List[str]:
    """
    Backward compatible helper: returns the missing enrich keys.
    Prefer `compute_scholar_completeness()` for a richer view.
    """
    comp = compute_scholar_completeness(report)
    missing = comp.get("missing")
    if isinstance(missing, list):
        # map collaborator key name to legacy field name
        out: List[str] = []
        for k in missing:
            if k == "collaborator":
                out.append("most_frequent_collaborator")
            else:
                out.append(k)
        return out
    return []


def _job_status_callback(ctx: JobContext):  # type: ignore[no-untyped-def]
    def cb(msg: Any) -> None:
        if ctx.cancelled():
            return
        if isinstance(msg, dict):
            message = str(msg.get("message", ""))
            raw_progress = msg.get("progress")
            try:
                p = float(raw_progress) if raw_progress is not None else None
            except (TypeError, ValueError):
                p = None
            ctx.progress(message=message, step="enrich", progress=p)
            return
        ctx.progress(message=str(msg), step="enrich", progress=None)

    return cb


def schedule_cache_repair_job(
    *,
    manager: JobManager,
    user_id: str,
    scholar_id: str,
) -> str:
    job_id = manager.create_or_get(
        job_key=f"scholar_cache_repair:{user_id}:{scholar_id}",
        kind="scholar_cache_repair",
        user_id=user_id,
    )

    def run(ctx: JobContext) -> Dict[str, Any]:
        ctx.progress(message="Loading cached report...", step="load_cache", progress=1.0)

        # Use ScholarService for deps (fetcher/analyzer); avoid importing DB helpers here.
        api_token = API_KEYS.get("CRAWLBASE_API_TOKEN")
        service = ScholarService(use_crawlbase=bool(api_token), api_token=api_token, use_cache=True, cache_max_age_days=30)

        from server.api.scholar.db_cache import get_scholar_from_cache_no_log, save_scholar_to_cache

        cached = get_scholar_from_cache_no_log(scholar_id, max_age_days=30)
        if not isinstance(cached, dict):
            raise RuntimeError(f"cached report not found for scholar_id={scholar_id}")

        missing_before = detect_missing_enrich(cached)
        ctx.data(
            message="Cache loaded",
            step="cache_loaded",
            payload={"scholarId": scholar_id, "completeness": compute_scholar_completeness(cached), "missing": missing_before},
        )

        if not missing_before:
            urls = save_scholar_report(cached, scholar_id, session_id="cache_repair")
            urls["scholar_id"] = scholar_id
            return {"scholarId": scholar_id, "missing": [], "report": urls}

        ctx.progress(message="Repairing missing enrich fields...", step="repair", progress=5.0, payload={"missing": missing_before})

        repaired = validate_and_complete_cache(
            cached,
            service.data_fetcher,
            service.analyzer,
            callback=_job_status_callback(ctx),
            cancel_event=ctx.cancel_event,
        )

        ctx.progress(message="Saving repaired report to DB cache...", step="save_cache", progress=95.0)
        save_scholar_to_cache(repaired, scholar_id)

        urls = save_scholar_report(repaired, scholar_id, session_id="cache_repair")
        urls["scholar_id"] = scholar_id

        completeness = compute_scholar_completeness(repaired)
        missing_after = detect_missing_enrich(repaired)
        ctx.data(
            message="Cache repair completed",
            step="repaired",
            payload={"scholarId": scholar_id, "completeness": completeness, "missing_after": missing_after, "report": urls},
        )

        return {"scholarId": scholar_id, "completeness": completeness, "missing_after": missing_after, "report": urls}

    manager.submit(job_id, run)
    return job_id


def schedule_full_refresh_job(
    *,
    manager: JobManager,
    user_id: str,
    scholar_id: str,
) -> str:
    job_id = manager.create_or_get(
        job_key=f"scholar_full_refresh:{user_id}:{scholar_id}",
        kind="scholar_full_refresh",
        user_id=user_id,
    )

    def run(ctx: JobContext) -> Dict[str, Any]:
        ctx.progress(message="Starting full refresh...", step="start", progress=1.0)

        api_token = API_KEYS.get("CRAWLBASE_API_TOKEN")
        report = run_scholar_analysis(
            scholar_id=scholar_id,
            use_crawlbase=True,
            api_token=api_token,
            callback=_job_status_callback(ctx),
            use_cache=True,
            cache_max_age_days=30,
            cancel_event=ctx.cancel_event,
            user_id=user_id,
        )
        if not isinstance(report, dict):
            raise RuntimeError("full refresh failed: empty report")

        urls = save_scholar_report(report, scholar_id, session_id="full_refresh")
        urls["scholar_id"] = scholar_id
        completeness = compute_scholar_completeness(report)
        missing_after = detect_missing_enrich(report)

        ctx.data(
            message="Full refresh completed",
            step="completed",
            payload={"scholarId": scholar_id, "completeness": completeness, "missing_after": missing_after, "report": urls},
        )

        return {"scholarId": scholar_id, "completeness": completeness, "missing_after": missing_after, "report": urls}

    manager.submit(job_id, run)
    return job_id
