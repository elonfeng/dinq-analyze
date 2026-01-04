from __future__ import annotations
from server.analyze.meta_utils import ensure_meta

import os
from typing import Any, Callable, Dict, Optional, Tuple

from server.services.scholar.scholar_service import ScholarService, run_scholar_analysis
from server.utils.profile_utils import get_random_avatar, get_random_description

try:
    from server.api.scholar.db_cache import get_scholar_from_cache  # type: ignore
except Exception:  # noqa: BLE001
    get_scholar_from_cache = None  # type: ignore


ProgressFn = Callable[[str, str, Optional[Dict[str, Any]]], None]


def _emit(progress: Optional[ProgressFn], step: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
    if progress:
        progress(step, message, data)


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def _build_service(*, use_cache: bool, cache_max_age_days: int) -> ScholarService:
    api_token = (os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or "").strip() or None
    use_crawlbase = _bool_env("DINQ_SCHOLAR_USE_CRAWLBASE", default=bool(api_token))
    return ScholarService(
        use_crawlbase=bool(use_crawlbase and api_token),
        api_token=api_token,
        use_cache=use_cache,
        cache_max_age_days=cache_max_age_days,
    )


def _resolve_author_info(
    service: ScholarService, *, scholar_id: Optional[str], researcher_name: Optional[str]
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    sid = str(scholar_id or "").strip() or None
    name = str(researcher_name or "").strip() or None

    if sid:
        return {"scholar_id": sid}, sid

    # Best-effort Tavily resolution (optional).
    if name and service.tvly_client is not None:
        try:
            resp = service.tvly_client.search(query=name)
            extracted = service.extract_scholar_id_from_tavily_response(resp)
            extracted = str(extracted or "").strip() or None
            if extracted:
                return {"scholar_id": extracted}, extracted
        except Exception:
            pass

    author_info = service.data_fetcher.search_researcher(name=name, scholar_id=None) if name else None
    if not isinstance(author_info, dict) or not author_info:
        return None, None
    sid = str(author_info.get("scholar_id") or "").strip() or None
    return author_info, sid


def run_scholar_preview(
    *,
    scholar_id: Optional[str],
    researcher_name: Optional[str],
    user_id: Optional[str],
    progress: Optional[ProgressFn] = None,
) -> Dict[str, Any]:
    """
    Phase -1: immediate skeleton prefill (no network).
    """
    name = str(researcher_name or scholar_id or "Unknown").strip() or "Unknown"
    _emit(progress, "preview.scholar", "Scholar preview ready", {"name": name, "scholar_id": scholar_id})
    return ensure_meta({"researcher": {"name": name, "scholar_id": scholar_id}, "publication_stats": {}}, source="scholar_preview", preserve_empty=True)


def run_scholar_page0(
    *,
    scholar_id: Optional[str],
    researcher_name: Optional[str],
    user_id: Optional[str],
    progress: Optional[ProgressFn] = None,
) -> Dict[str, Any]:
    """
    Phase 0: fetch researcher core info + a small slice of papers for fast-first UX.
    """
    cache_max_age_days = max(0, min(_int_env("DINQ_SCHOLAR_CACHE_MAX_AGE_DAYS", 3), 30))
    max_papers = max(0, _int_env("DINQ_SCHOLAR_MAX_PAPERS_PAGE0", 30))

    service = _build_service(use_cache=True, cache_max_age_days=cache_max_age_days)
    author_info, resolved_id = _resolve_author_info(service, scholar_id=scholar_id, researcher_name=researcher_name)
    if not author_info or not resolved_id:
        return {}

    # Fast path: return cached payload if available (no heavy repair for page0).
    if service.use_cache and get_scholar_from_cache is not None:
        try:
            cached = get_scholar_from_cache(resolved_id, cache_max_age_days, name=researcher_name)  # type: ignore[misc]
            if isinstance(cached, dict) and cached:
                _emit(progress, "scholar.cache_hit", "Scholar cache hit (page0)", {"scholar_id": resolved_id})
                return cached
        except Exception:
            pass

    _emit(progress, "scholar.fetch_profile", "Retrieving scholar profile (page0)...", {"max_papers": max_papers})
    author_data = service.data_fetcher.get_full_profile(author_info, max_papers=int(max_papers))
    if not isinstance(author_data, dict) or not author_data:
        return {}

    # Minimal publication stats; full stats come from resource.scholar.full.
    pub_stats = service.analyzer.analyze_publications(author_data) or {}
    if not isinstance(pub_stats, dict):
        pub_stats = {}

    name = str(author_data.get("name") or researcher_name or resolved_id or "").strip()
    avatar_url = get_random_avatar()
    description = get_random_description(name) if name else "A brilliant researcher exploring the frontiers of knowledge."

    report = ensure_meta({
        "researcher": {
            "name": name,
            "abbreviated_name": author_data.get("abbreviated_name", ""),
            "affiliation": author_data.get("affiliation", ""),
            "email": author_data.get("email", ""),
            "research_fields": author_data.get("research_fields", []),
            "total_citations": author_data.get("total_citations", 0),
            "citations_5y": author_data.get("citations_5y", 0),
            "h_index": author_data.get("h_index", 0),
            "h_index_5y": author_data.get("h_index_5y", 0),
            "yearly_citations": author_data.get("yearly_citations", {}),
            "scholar_id": resolved_id,
            "avatar": avatar_url,
            "description": description,
        },
        "publication_stats": pub_stats,
    }, source="scholar_page0", preserve_empty=True)
    return report


def run_scholar_full(
    *,
    scholar_id: Optional[str],
    researcher_name: Optional[str],
    user_id: Optional[str],
    progress: Optional[ProgressFn] = None,
) -> Dict[str, Any]:
    """
    Phase 1: full scholar report (heavier compute).
    """
    api_token = (os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or "").strip() or None
    use_crawlbase = _bool_env("DINQ_SCHOLAR_USE_CRAWLBASE", default=bool(api_token))
    cache_max_age_days = max(0, min(_int_env("DINQ_SCHOLAR_CACHE_MAX_AGE_DAYS", 3), 30))

    _emit(progress, "scholar.full", "Running full scholar analysis...", {"use_crawlbase": bool(use_crawlbase and api_token)})
    return (
        run_scholar_analysis(
            researcher_name=researcher_name if not scholar_id else None,
            scholar_id=scholar_id,
            use_crawlbase=bool(use_crawlbase and api_token),
            api_token=api_token,
            callback=None,
            use_cache=True,
            cache_max_age_days=cache_max_age_days,
            cancel_event=None,
            user_id=user_id,
        )
        or {}
    )


def run_scholar_base(
    *,
    scholar_id: Optional[str],
    researcher_name: Optional[str],
    user_id: Optional[str],
    progress: Optional[ProgressFn] = None,
) -> Dict[str, Any]:
    """
    Compatibility resource: base report (no enrich). Currently aliases page0.
    """
    return run_scholar_page0(scholar_id=scholar_id, researcher_name=researcher_name, user_id=user_id, progress=progress)


def estimate_scholar_level_fast(
    *,
    report: Dict[str, Any],
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Career level evaluation.

    Note: Despite the historical name, this uses the upstream scholar career-level logic
    (`account.juris_people.three_card_juris_people` via `get_career_level_info`) for parity.
    """
    from server.services.scholar.career_level_service import get_career_level_info

    try:
        level = get_career_level_info(report, from_cache=False, callback=None) or {}
    except Exception:
        level = {}
    return level if isinstance(level, dict) else {}

