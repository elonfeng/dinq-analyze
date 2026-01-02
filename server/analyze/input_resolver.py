"""
Source-specific input normalization for unified analyze API.

Goals:
- Provide a consistent public contract for clients: `input.content` is the primary field.
- Keep backward compatibility with older per-source keys (e.g. scholar_id/username/name).
- Centralize parsing rules so docs + behavior stay aligned.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse


# Scholar user IDs typically end with "AAAAJ" (sometimes "AAAAAJ").
# Keep this strict to avoid misclassifying arbitrary single-token names as IDs.
_SCHOLAR_ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,26}A{4,6}J$")
_GITHUB_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37})$")
_TWITTER_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")

SOURCE_INPUT_KEYS: Dict[str, tuple[str, ...]] = {
    # Public contract: prefer input.content for all sources.
    # Legacy per-source keys are still accepted for backward compatibility.
    "scholar": ("content", "scholar_id", "id", "query", "name"),
    "github": ("content", "username", "login"),
    "linkedin": ("content", "url", "name", "person_name", "linkedin_id"),
    "twitter": ("content", "username"),
    "openreview": ("content", "username", "email"),
    "huggingface": ("content", "username"),
    "youtube": ("content", "channel_id", "channel"),
}


def _first_nonempty_str(payload: Dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _strip_subject_key_prefix(source: str, value: str) -> str:
    """
    Allow feeding back `subject_key` values (e.g. "login:mdo") as input.content.

    This supports the "frontend routes by subject_key" flow:
      - create -> returns subject_key
      - page URL stores subject_key
      - reload -> call create again with input.content=subject_key
    """

    src = (source or "").strip().lower()
    raw = str(value or "").strip()
    if not raw:
        return ""

    lowered = raw.lower()
    prefix_map = {
        "scholar": ("id:",),
        "github": ("login:",),
        "linkedin": ("url:",),
        "twitter": ("username:",),
        "openreview": ("id:",),
        "huggingface": ("username:",),
        "youtube": ("channel:",),
    }
    for p in prefix_map.get(src, ()):
        if lowered.startswith(p):
            return raw[len(p):].strip()
    return raw


def _parse_url_loose(value: str):
    raw = (value or "").strip()
    if not raw:
        return urlparse("")
    if "://" in raw:
        return urlparse(raw)
    if raw.startswith("//"):
        return urlparse(f"https:{raw}")
    # Support "github.com/xxx" (missing scheme)
    return urlparse(f"https://{raw.lstrip('/')}")


def resolve_scholar_identity(input_payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (scholar_id, query_name).

    Priority:
    1) scholar_id / id
    2) content/query/name:
       - Scholar profile URL -> extract `user=...`
       - Looks like scholar_id -> treat as scholar_id
       - Otherwise -> treat as name query
    """

    scholar_id = _first_nonempty_str(input_payload, ("scholar_id", "id"))
    if scholar_id:
        return scholar_id, None

    content = _first_nonempty_str(input_payload, ("content", "query", "name"))
    if not content:
        return None, None

    # Support Scholar profile URLs and shorthand forms like:
    # - https://scholar.google.com/citations?user=...&hl=en
    # - scholar?user=...
    # - citations?user=...
    # We only accept IDs matching the Scholar token regex to avoid misclassifying random URLs.
    try:
        parsed = _parse_url_loose(content)
        qs = parse_qs(parsed.query or "")
        user = (qs.get("user") or [None])[0]
        if user:
            user = str(user).strip()
            if _SCHOLAR_ID_RE.match(user):
                return user, None
    except Exception:  # noqa: BLE001
        pass

    # Heuristic: treat compact token-like content as scholar_id.
    if " " not in content and _SCHOLAR_ID_RE.match(content):
        return content, None

    return None, content


def resolve_github_username(input_payload: Dict[str, Any]) -> str:
    return _first_nonempty_str(input_payload, ("username", "login", "content"))


def resolve_linkedin_content(input_payload: Dict[str, Any]) -> str:
    # `content` is preferred; keep url/name/person_name for backward compat.
    return _first_nonempty_str(input_payload, ("content", "url", "name", "person_name", "linkedin_id"))


def resolve_twitter_username(input_payload: Dict[str, Any]) -> str:
    raw = _first_nonempty_str(input_payload, ("username", "content"))
    if raw.startswith("@"):
        raw = raw[1:]
    if "twitter.com/" in raw or "x.com/" in raw:
        try:
            parsed = _parse_url_loose(raw)
            parts = [p for p in (parsed.path or "").split("/") if p]
            if parts:
                return parts[0].lstrip("@")
        except Exception:  # noqa: BLE001
            return raw
    return raw


def resolve_openreview_identifier(input_payload: Dict[str, Any]) -> Tuple[str, str]:
    """
    Return (kind, value), where kind is "email" or "username".
    """

    raw = _first_nonempty_str(input_payload, ("username", "email", "content"))
    if "@" in raw:
        return "email", raw
    return "username", raw


def resolve_huggingface_username(input_payload: Dict[str, Any]) -> str:
    raw = _first_nonempty_str(input_payload, ("username", "content"))
    if "huggingface.co/" in raw:
        try:
            parsed = _parse_url_loose(raw)
            parts = [p for p in (parsed.path or "").split("/") if p]
            if parts:
                return parts[0]
        except Exception:  # noqa: BLE001
            return raw
    return raw


def resolve_youtube_channel_input(input_payload: Dict[str, Any]) -> str:
    # YouTubeAnalyzer accepts: channel_id / url / handle / name.
    return _first_nonempty_str(input_payload, ("channel_id", "channel", "content"))


def normalize_input_payload(source: str, input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize client input into a stable, source-specific canonical form.

    - Keeps backward compatibility: accepts legacy keys but always sets `content`.
    - Extracts IDs from URLs where possible (e.g. scholar/github/twitter/huggingface).
    """

    src = (source or "").strip().lower()
    payload: Dict[str, Any] = dict(input_payload or {})

    keys = SOURCE_INPUT_KEYS.get(src, ("content",))
    raw = _first_nonempty_str(payload, keys)
    if raw:
        payload["content"] = _strip_subject_key_prefix(src, raw)

    if not raw:
        return payload

    if src == "scholar":
        scholar_id, query = resolve_scholar_identity(payload)
        if scholar_id:
            payload["content"] = scholar_id
        elif query:
            payload["content"] = query
        return payload

    if src == "github":
        value = resolve_github_username(payload).strip()
        if "github.com/" in value or value.startswith("github.com"):
            try:
                parsed = _parse_url_loose(value)
                parts = [p for p in (parsed.path or "").split("/") if p]
                if parts:
                    value = parts[0]
            except Exception:  # noqa: BLE001
                pass
        payload["content"] = value
        return payload

    if src == "linkedin":
        value = resolve_linkedin_content(payload).strip()
        if "linkedin.com/" in value or value.startswith("linkedin.com"):
            try:
                parsed = _parse_url_loose(value)
                cleaned = parsed._replace(query="", fragment="").geturl()
                payload["content"] = cleaned.rstrip("/")
                return payload
            except Exception:  # noqa: BLE001
                pass
        payload["content"] = value
        return payload

    if src == "twitter":
        value = resolve_twitter_username(payload).strip()
        # Best-effort validation; keep raw if it doesn't look like a handle.
        payload["content"] = value if _TWITTER_USERNAME_RE.match(value) else value
        return payload

    if src == "openreview":
        _, value = resolve_openreview_identifier(payload)
        payload["content"] = value.strip()
        return payload

    if src == "huggingface":
        payload["content"] = resolve_huggingface_username(payload).strip()
        return payload

    if src == "youtube":
        payload["content"] = resolve_youtube_channel_input(payload).strip()
        return payload

    payload["content"] = raw.strip()
    return payload
