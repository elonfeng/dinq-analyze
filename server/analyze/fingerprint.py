"""
External change fingerprints for incremental refresh.

If a fingerprint is available and unchanged, we can safely reuse a cached run even
after its TTL expires (within a configured max-stale window).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests


def get_fingerprint(*, source: str, subject_key: str, canonical_input: Optional[Dict[str, Any]] = None) -> Optional[str]:
    src = (source or "").strip().lower()
    key = (subject_key or "").strip()
    if not src or not key:
        return None

    if src == "github":
        login = _extract_github_login(key, canonical_input)
        if not login:
            return None
        return _github_latest_event_fingerprint(login)

    if src == "scholar":
        scholar_id = _extract_scholar_id(key, canonical_input)
        if not scholar_id:
            return None
        return _scholar_profile_fingerprint(scholar_id)

    return None


def fingerprint_from_payload(*, source: str, payload: Any) -> Optional[str]:
    """
    Compute a stable fingerprint from an already-fetched payload (no network).

    This is used when saving a run so we don't need an extra request just to compute a fingerprint.
    Later, `get_fingerprint()` can compute the current fingerprint (with a cheap request) for revalidation.
    """

    src = (source or "").strip().lower()
    if src != "scholar":
        return None

    if not isinstance(payload, dict):
        return None
    researcher = payload.get("researcher") if isinstance(payload.get("researcher"), dict) else None
    if researcher is None and isinstance(payload.get("researcherProfile"), dict):
        researcher = (payload.get("researcherProfile") or {}).get("researcherInfo")
    if not isinstance(researcher, dict):
        researcher = {}

    def _int(v: Any) -> int:
        try:
            return int(v or 0)
        except Exception:
            try:
                return int(float(str(v).strip()))
            except Exception:
                return 0

    # Support both legacy raw report keys and formatted report keys.
    if "totalCitations" in researcher or "hIndex" in researcher:
        total = _int(researcher.get("totalCitations"))
        c5 = _int(researcher.get("citations5y"))
        h = _int(researcher.get("hIndex"))
        h5 = _int(researcher.get("hIndex5y"))
        yearly = researcher.get("yearlyCitations") if isinstance(researcher.get("yearlyCitations"), dict) else {}
    else:
        total = _int(researcher.get("total_citations"))
        c5 = _int(researcher.get("citations_5y"))
        h = _int(researcher.get("h_index"))
        h5 = _int(researcher.get("h_index_5y"))
        yearly = researcher.get("yearly_citations") if isinstance(researcher.get("yearly_citations"), dict) else {}
    years = []
    for y in yearly.keys():
        try:
            years.append(int(str(y)))
        except Exception:
            continue
    years = sorted(set(years))[-3:]
    ypart = ",".join([f"{y}:{_int(yearly.get(str(y)) or yearly.get(y) or 0)}" for y in years])
    return f"cit={total}|cit5={c5}|h={h}|h5={h5}|y={ypart}"


def _extract_github_login(subject_key: str, canonical_input: Optional[Dict[str, Any]]) -> str:
    if subject_key.startswith("login:"):
        return subject_key.split(":", 1)[1].strip()
    if canonical_input:
        content = str((canonical_input or {}).get("content") or "").strip()
        if content:
            return content
    return ""


def _extract_scholar_id(subject_key: str, canonical_input: Optional[Dict[str, Any]]) -> str:
    if subject_key.startswith("id:"):
        return subject_key.split(":", 1)[1].strip()
    if canonical_input:
        content = str((canonical_input or {}).get("content") or "").strip()
        if content:
            return content
    return ""


def _github_latest_event_fingerprint(login: str) -> Optional[str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(
            f"https://api.github.com/users/{login}/events/public",
            params={"per_page": 1},
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            items = resp.json() or []
            if isinstance(items, list) and items:
                ev = items[0] if isinstance(items[0], dict) else {}
                ev_id = str(ev.get("id") or "").strip()
                created_at = str(ev.get("created_at") or "").strip()
                ev_type = str(ev.get("type") or "").strip()
                if ev_id or created_at:
                    return f"{ev_id}|{created_at}|{ev_type}"
    except Exception:  # noqa: BLE001
        return None

    # Fallback: profile updated_at (less reliable, but better than nothing)
    try:
        resp = requests.get(
            f"https://api.github.com/users/{login}",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json() or {}
            updated_at = str(data.get("updated_at") or "").strip()
            public_repos = str(data.get("public_repos") or "")
            followers = str(data.get("followers") or "")
            if updated_at:
                return f"updated_at:{updated_at}|repos:{public_repos}|followers:{followers}"
    except Exception:  # noqa: BLE001
        return None

    return None


def _scholar_profile_fingerprint(scholar_id: str) -> Optional[str]:
    """
    Best-effort Scholar change fingerprint using a single profile page fetch.

    It intentionally uses only the lightweight, high-signal metrics we already store in the report:
    - total citations / 5y citations / h-index / 5y h-index
    - last 3 years of citation counts
    """

    try:
        from server.services.scholar.data_fetcher import ScholarDataFetcher

        api_token = (os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or "").strip() or None
        use_crawlbase = bool(os.getenv("DINQ_SCHOLAR_USE_CRAWLBASE")) or bool(api_token)
        fetcher = ScholarDataFetcher(use_crawlbase=use_crawlbase, api_token=api_token)

        url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en&oi=ao"
        html = fetcher.fetch_html(url, cancel_event=None, user_id=None)
        parsed = fetcher.parse_google_scholar_html(html, page_index=0, first_page=True) if html else None
        if not isinstance(parsed, dict):
            return None

        def _int(v: Any) -> int:
            try:
                return int(str(v).strip())
            except Exception:
                return 0

        total = _int(parsed.get("total_citations"))
        c5 = _int(parsed.get("citations_5y"))
        h = _int(parsed.get("h_index"))
        h5 = _int(parsed.get("h_index_5y"))

        yearly = parsed.get("yearly_citations") if isinstance(parsed.get("yearly_citations"), dict) else {}
        years = []
        for y in yearly.keys():
            try:
                years.append(int(str(y)))
            except Exception:
                continue
        years = sorted(set(years))[-3:]
        ypart = ",".join([f"{y}:{_int(yearly.get(str(y)) or yearly.get(y))}" for y in years])

        return f"cit={total}|cit5={c5}|h={h}|h5={h5}|y={ypart}"
    except Exception:  # noqa: BLE001
        return None
