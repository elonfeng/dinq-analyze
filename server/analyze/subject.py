"""
Subject resolution for unified analysis.

Purpose:
- Convert a client input payload into a stable (source, subject_key) pair so we can
  reuse cached results across jobs and support stale-while-revalidate (SWR).
"""

from __future__ import annotations

import re
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse, urlunparse


# Scholar user IDs typically end with "AAAAJ" (sometimes "AAAAAJ").
# Keep this strict to avoid misclassifying arbitrary single-token names as IDs.
_SCHOLAR_ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,26}A{4,6}J$")
_GITHUB_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37})$")


def _parse_url_loose(value: str):
    raw = (value or "").strip()
    if not raw:
        return urlparse("")
    if "://" in raw:
        return urlparse(raw)
    if raw.startswith("//"):
        return urlparse(f"https:{raw}")
    return urlparse(f"https://{raw.lstrip('/')}")


def _canonicalize_url(value: str) -> str:
    """
    Best-effort URL canonicalization for cache keys:
    - force https scheme
    - drop query/fragment
    - normalize host casing and drop leading "www."
    - strip trailing "/"
    """

    parsed = _parse_url_loose(value)
    host = (parsed.netloc or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    path = (parsed.path or "").strip()
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")
    return urlunparse(("https", host, path, "", "", ""))


def resolve_subject_key(source: str, input_payload: Dict[str, Any]) -> str:
    """
    Resolve a canonical subject key for caching.

    The returned string is stable and namespaced (e.g. "id:...", "login:...", "url:...").
    """

    src = (source or "").strip().lower()
    content = str((input_payload or {}).get("content") or "").strip()
    if not content:
        return ""

    if src == "scholar":
        # Scholar URL -> extract `user=...` for stable caching.
        if "scholar.google" in content and "citations" in content:
            try:
                parsed = _parse_url_loose(content)
                qs = parse_qs(parsed.query or "")
                user = (qs.get("user") or [None])[0]
                if user and isinstance(user, str) and _SCHOLAR_ID_RE.match(user.strip()):
                    return f"id:{user.strip()}"
            except Exception:
                pass
        if " " not in content and _SCHOLAR_ID_RE.match(content):
            return f"id:{content}"
        return f"name:{content}"

    if src == "github":
        login = content.strip()
        if "github.com" in login.lower() or "/" in login:
            try:
                parsed = _parse_url_loose(login)
                parts = [p for p in (parsed.path or "").split("/") if p]
                if parts:
                    login = parts[0].strip()
            except Exception:
                pass
        if _GITHUB_LOGIN_RE.match(login):
            return f"login:{login.lower()}"
        return f"query:{content.strip()}"

    if src == "linkedin":
        if "linkedin.com" in content.lower():
            try:
                url = _canonicalize_url(content)
                if url:
                    return f"url:{url}"
            except Exception:
                return f"url:{content}"
            return f"url:{content}"
        return f"name:{content}"

    if src == "twitter":
        # input_resolver already strips '@' and parses URL when possible.
        return f"username:{content.lower()}"

    if src == "openreview":
        # May be email or profile id
        key = content.lower()
        return f"id:{key}"

    if src == "huggingface":
        return f"username:{content.lower()}"

    if src == "youtube":
        # channel_id / handle / url all live in content.
        return f"channel:{content}"

    return f"content:{content}"
