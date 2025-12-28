"""
Optional freeform input resolver (preflight) for /api/analyze.

Goal:
- When clients send ambiguous natural-language input (e.g. just a person name),
  return candidate entities for user confirmation before starting an analysis job.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from urllib.parse import parse_qs, urlparse, urlunparse

from src.models.db import AnalysisArtifactCache
from src.utils.db_utils import get_db_session

_GITHUB_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37})$")
# Scholar user IDs typically end with "AAAAJ" (sometimes "AAAAAJ").
# Keep this strict to avoid misclassifying arbitrary single-token names as IDs.
_SCHOLAR_ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,26}A{4,6}J$")
_LINKEDIN_PROFILE_PATH_RE = re.compile(r"^/(?:in|pub)/[^/?#]+/?$", re.IGNORECASE)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def is_ambiguous_input(source: str, content: str) -> bool:
    """
    Heuristic "is ambiguous" detector.

    Used by `/api/analyze` to decide whether an input is already a stable identifier
    (ID/login/profile URL) or needs candidate resolution for cache safety.
    """

    src = (source or "").strip().lower()
    text = (content or "").strip()
    if not text:
        return False
    if "http://" in text or "https://" in text:
        return False

    if src == "scholar":
        # If it's not a stable scholar_id, treat as ambiguous and require resolution.
        return not _SCHOLAR_ID_RE.match(text)
    if src == "github":
        return (" " in text) or (not _GITHUB_LOGIN_RE.match(text))
    if src == "linkedin":
        # Require a stable profile URL for caching; non-URL inputs need resolution.
        return "linkedin.com" not in text.lower()
    return " " in text and len(text) >= 12


def resolve_candidates(source: str, content: str, *, user_id: str) -> List[Dict[str, Any]]:
    """
    Return a list of candidates for user confirmation.

    Each candidate is:
      { "label": "...", "input": { "content": "..." }, "meta": {...} }
    """

    src = (source or "").strip().lower()
    text = (content or "").strip()
    limit = max(1, min(_int_env("DINQ_ANALYZE_FREEFORM_MAX_CANDIDATES", 5), 10))

    cache_key = _freeform_candidates_cache_key(src, text, limit=limit)
    if cache_key and _freeform_cache_enabled():
        cached = _freeform_cache_get_candidates(cache_key)
        if cached is not None:
            return cached

    if src == "github":
        candidates = _resolve_github_candidates(text, limit=limit)
        _freeform_cache_maybe_set(cache_key, candidates)
        return candidates
    if src == "scholar":
        candidates = _resolve_scholar_candidates(text, user_id=user_id, limit=limit)
        _freeform_cache_maybe_set(cache_key, candidates)
        return candidates
    if src == "linkedin":
        candidates = _resolve_linkedin_candidates(text, limit=limit)
        _freeform_cache_maybe_set(cache_key, candidates)
        return candidates

    # Not supported yet (needs platform search / deterministic resolver)
    return []


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_freeform_query(text: str) -> str:
    return " ".join((text or "").strip().split()).lower()


def _freeform_cache_enabled() -> bool:
    raw = os.getenv("DINQ_ANALYZE_FREEFORM_CACHE_ENABLED")
    if raw is not None:
        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    # Default: enable in production deployments only.
    return (os.getenv("DINQ_ENV") or "").strip().lower() == "production"


def _freeform_candidates_cache_key(source: str, query: str, *, limit: int) -> str:
    src = (source or "").strip().lower()
    q = _normalize_freeform_query(query)
    if not src or not q:
        return ""
    raw = f"freeform_candidates:v1:{src}:{limit}:{q}"
    return _sha256_hex(raw)


def _freeform_cache_get_candidates(cache_key: str) -> Optional[List[Dict[str, Any]]]:
    if not cache_key:
        return None

    try:
        with get_db_session() as session:
            rec = session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == cache_key).first()
            if rec is None:
                return None
            expires_at = getattr(rec, "expires_at", None)
            if expires_at is not None and expires_at <= datetime.utcnow():
                return None
            payload = rec.payload
            if not isinstance(payload, list):
                return None
            # Best-effort: ensure each candidate is a dict.
            candidates: List[Dict[str, Any]] = []
            for it in payload:
                if isinstance(it, dict):
                    candidates.append(it)
            return candidates
    except Exception:  # noqa: BLE001
        return None


def _freeform_cache_maybe_set(cache_key: str, candidates: List[Dict[str, Any]]) -> None:
    if not cache_key or not _freeform_cache_enabled():
        return

    ttl_default = 7 * 24 * 60 * 60
    empty_ttl_default = 5 * 60
    ttl_seconds = _int_env("DINQ_ANALYZE_FREEFORM_CACHE_TTL_SECONDS", ttl_default)
    empty_ttl_seconds = _int_env("DINQ_ANALYZE_FREEFORM_EMPTY_CACHE_TTL_SECONDS", empty_ttl_default)

    ttl = int(ttl_seconds if candidates else empty_ttl_seconds)
    ttl = max(0, min(ttl, 30 * 24 * 60 * 60))
    if ttl <= 0:
        return

    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=ttl)

    try:
        with get_db_session() as session:
            rec = session.query(AnalysisArtifactCache).filter(AnalysisArtifactCache.artifact_key == cache_key).first()
            if rec is None:
                rec = AnalysisArtifactCache(
                    artifact_key=cache_key,
                    kind="freeform_candidates",
                    payload=candidates,
                    created_at=now,
                    expires_at=expires_at,
                    meta={"ttl_seconds": ttl},
                )
                session.add(rec)
            else:
                rec.kind = "freeform_candidates"
                rec.payload = candidates
                rec.created_at = now
                rec.expires_at = expires_at
                rec.meta = {"ttl_seconds": ttl}
    except Exception:  # noqa: BLE001
        return


def _resolve_github_candidates(query: str, *, limit: int) -> List[Dict[str, Any]]:
    if not query:
        return []
    try:
        headers = {"Accept": "application/vnd.github+json"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = requests.get(
            "https://api.github.com/search/users",
            params={"q": query, "per_page": limit},
            headers=headers,
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        data = resp.json() or {}
        items = data.get("items") or []
        candidates: List[Dict[str, Any]] = []
        for it in items[:limit]:
            login = (it.get("login") or "").strip()
            if not login:
                continue
            url = (it.get("html_url") or "").strip()
            label = f"{login}" + (f" ({url})" if url else "")
            candidates.append(
                {
                    "label": label,
                    "input": {"content": login},
                    "meta": {
                        "login": login,
                        "url": url,
                        "avatar": it.get("avatar_url"),
                        "score": it.get("score"),
                    },
                }
            )
        return candidates
    except Exception:  # noqa: BLE001
        return []


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _resolve_scholar_candidates(query: str, *, user_id: str, limit: int) -> List[Dict[str, Any]]:
    if not query:
        return []

    candidates = _resolve_scholar_candidates_via_tavily(query, limit=limit)
    if candidates:
        return candidates

    # Reuse the existing Scholar fetcher (scrapes search_authors results).
    try:
        from server.services.scholar.scholar_service import ScholarService

        api_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""
        use_crawlbase = _bool_env("DINQ_SCHOLAR_USE_CRAWLBASE", default=bool(api_token))

        service = ScholarService(use_crawlbase=use_crawlbase, api_token=(api_token or None), use_cache=False, cache_max_age_days=0)
        results = service.data_fetcher.search_author_by_name(query, user_id=user_id) or []
        candidates: List[Dict[str, Any]] = []
        for it in results[:limit]:
            scholar_id = (it.get("scholar_id") or "").strip()
            name = (it.get("name") or "").strip()
            affiliation = (it.get("affiliation") or "").strip()
            if not scholar_id:
                continue
            label = name or scholar_id
            if affiliation:
                label = f"{label} - {affiliation}"
            candidates.append(
                {
                    "label": label,
                    "input": {"content": scholar_id},
                    "meta": {
                        "name": name,
                        "affiliation": affiliation,
                        "interests": it.get("interests"),
                        "profile_url": it.get("profile_url"),
                    },
                }
            )
        return candidates
    except Exception:  # noqa: BLE001
        return []


def _extract_scholar_id_from_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw.lstrip('/')}"
    try:
        parsed = urlparse(raw)
    except Exception:  # noqa: BLE001
        return ""

    host = (parsed.netloc or "").lower()
    if "scholar.google." not in host:
        return ""

    path = (parsed.path or "").lower()
    if "citations" not in path:
        return ""

    try:
        qs = parse_qs(parsed.query or "")
    except Exception:  # noqa: BLE001
        qs = {}

    user = (qs.get("user") or [None])[0]
    scholar_id = str(user or "").strip()
    if not scholar_id or not _SCHOLAR_ID_RE.match(scholar_id):
        return ""
    return scholar_id


def _resolve_scholar_candidates_via_tavily(query: str, *, limit: int) -> List[Dict[str, Any]]:
    """
    Resolve Google Scholar profile candidates for a person-name query.

    Strategy:
    - Use Tavily search if `TAVILY_API_KEY` is configured.
    - Filter to scholar.google.* citations profiles with `user=` and return candidate input.content = scholar_id.
    """

    text = (query or "").strip()
    if not text:
        return []

    api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
    if not api_key:
        return []

    try:
        from tavily import TavilyClient  # type: ignore

        client = TavilyClient(api_key)
        search_query = f'site:scholar.google.com/citations "{text}"'
        try:
            resp = client.search(query=search_query, max_results=max(limit * 3, limit))  # type: ignore[arg-type]
        except TypeError:
            resp = client.search(query=search_query)  # type: ignore[arg-type]
        results = (resp or {}).get("results") if isinstance(resp, dict) else None
        if not isinstance(results, list):
            return []
    except Exception:  # noqa: BLE001
        return []

    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for it in results:
        if len(candidates) >= limit:
            break
        if not isinstance(it, dict):
            continue

        url = str(it.get("url") or "").strip()
        scholar_id = _extract_scholar_id_from_url(url)
        if not scholar_id or scholar_id in seen:
            continue
        seen.add(scholar_id)

        title = str(it.get("title") or "").strip()
        label = title if title else scholar_id
        profile_url = f"https://scholar.google.com/citations?user={scholar_id}"
        candidates.append(
            {
                "label": label,
                "input": {"content": scholar_id},
                "meta": {
                    "scholar_id": scholar_id,
                    "profile_url": profile_url,
                    "title": title,
                    "snippet": it.get("content") or it.get("snippet"),
                },
            }
        )

    return candidates


def _clean_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw.lstrip('/')}"
    parsed = urlparse(raw)
    if not parsed.netloc:
        return ""
    cleaned = parsed._replace(query="", fragment="")
    return urlunparse(cleaned).rstrip("/")


def _is_linkedin_profile_url(url: str) -> bool:
    cleaned = _clean_url(url)
    if not cleaned:
        return False
    parsed = urlparse(cleaned)
    host = (parsed.netloc or "").lower()
    if not host.endswith("linkedin.com"):
        return False
    path = parsed.path or ""
    return bool(_LINKEDIN_PROFILE_PATH_RE.match(path))


def _resolve_linkedin_candidates(query: str, *, limit: int) -> List[Dict[str, Any]]:
    """
    Resolve LinkedIn profile candidates for a person-name query.

    Strategy:
    - Use Tavily search if `TAVILY_API_KEY` is configured.
    - Filter to linkedin.com/in|pub profiles and return as candidate input.content = profile URL.
    """

    text = (query or "").strip()
    if not text:
        return []

    api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
    if not api_key:
        return []

    # Tavily client is an optional dependency; keep this best-effort.
    try:
        from tavily import TavilyClient  # type: ignore

        client = TavilyClient(api_key)
        # Bias search towards personal profiles.
        search_query = f'site:linkedin.com/in "{text}"'
        try:
            resp = client.search(query=search_query, max_results=limit)  # type: ignore[arg-type]
        except TypeError:
            # Older client versions may not accept max_results.
            resp = client.search(query=search_query)  # type: ignore[arg-type]
        results = (resp or {}).get("results") if isinstance(resp, dict) else None
        if not isinstance(results, list):
            return []
    except Exception:  # noqa: BLE001
        return []

    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for it in results:
        if len(candidates) >= limit:
            break
        if not isinstance(it, dict):
            continue

        url = _clean_url(str(it.get("url") or ""))
        if not url or not _is_linkedin_profile_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)

        title = str(it.get("title") or "").strip()
        label = title if title else url
        candidates.append(
            {
                "label": label,
                "input": {"content": url},
                "meta": {
                    "url": url,
                    "title": title,
                    "snippet": it.get("content") or it.get("snippet"),
                },
            }
        )

    return candidates
