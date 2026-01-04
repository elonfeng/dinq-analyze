"""
Cache policy for unified analysis (cross-job reuse + SWR).
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Optional


_IGNORED_OPTION_KEYS = {
    # UI / preflight only
    "freeform",
    # Internal meta (does not affect analysis semantics)
    "_requested_cards",
    # Client hints (do not affect analysis semantics)
    "client_trace",
    # If added in the future: allow a request to bypass caches
    "force_refresh",
}


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_pipeline_version(source: Optional[str] = None) -> str:
    base = (os.getenv("DINQ_ANALYZE_PIPELINE_VERSION") or "v1").strip()
    if source:
        try:
            from server.analyze.handlers.registry import get_global_registry
            handler_hash = get_global_registry().get_version_hash(source)
            return f"{base}-h{handler_hash}"
        except Exception:
            pass
    return base


def normalize_run_options(options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract options that affect the analysis output.

    Non-semantic flags (like freeform preflight) must NOT affect run caching keys.
    """

    if not isinstance(options, dict):
        return {}
    cleaned: Dict[str, Any] = {}
    for k, v in options.items():
        key = str(k).strip()
        if not key or key in _IGNORED_OPTION_KEYS:
            continue
        cleaned[key] = v
    return cleaned


def compute_options_hash(options: Optional[Dict[str, Any]]) -> str:
    cleaned = normalize_run_options(options)
    raw = json.dumps(cleaned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_hex(raw)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def cache_ttl_seconds(source: str) -> int:
    """
    Full-report cache TTL.

    Per-source override: DINQ_ANALYZE_CACHE_TTL_SECONDS_<SOURCE>
    Global default: DINQ_ANALYZE_CACHE_TTL_SECONDS
    """

    src = (source or "").strip().upper()
    # Built-in defaults (only used when no env overrides exist).
    # Rationale: Scholar runs are expensive and (usually) don't change minute-to-minute.
    built_in_default = {
        "SCHOLAR": 3 * 24 * 3600,
        "LINKEDIN": 7 * 24 * 3600,
        # GitHub has a cheap external fingerprint; keep TTL moderate and rely on validate/max-stale for longer reuse.
        "GITHUB": 6 * 3600,
        "TWITTER": 24 * 3600,
        "OPENREVIEW": 7 * 24 * 3600,
        "HUGGINGFACE": 24 * 3600,
        "YOUTUBE": 24 * 3600,
    }.get(src, 24 * 3600)
    return max(
        0,
        _int_env(
            f"DINQ_ANALYZE_CACHE_TTL_SECONDS_{src}",
            _int_env("DINQ_ANALYZE_CACHE_TTL_SECONDS", built_in_default),
        ),
    )


def max_stale_seconds(source: str) -> int:
    """
    Max stale window for "fingerprint unchanged => reuse even if TTL expired".
    """

    src = (source or "").strip().upper()
    return max(
        0,
        _int_env(
            f"DINQ_ANALYZE_CACHE_MAX_STALE_SECONDS_{src}",
            _int_env("DINQ_ANALYZE_CACHE_MAX_STALE_SECONDS", 7 * 24 * 3600),
        ),
    )


def prefill_max_age_seconds(source: str) -> int:
    """
    Max age for serving cached content as "prefill" (UI only) while revalidating.
    """

    src = (source or "").strip().upper()
    return max(
        0,
        _int_env(
            f"DINQ_ANALYZE_PREFILL_MAX_AGE_SECONDS_{src}",
            _int_env("DINQ_ANALYZE_PREFILL_MAX_AGE_SECONDS", 7 * 24 * 3600),
        ),
    )


def is_cacheable_subject(*, source: str, subject_key: str) -> bool:
    """
    Best-effort guardrail: only cache when the subject_key is stable.

    Rationale:
    - Inputs like "name:..." / "query:..." are ambiguous and may resolve to different entities over time.
      Prefill/cross-job reuse for such keys risks showing wrong data.
    """

    src = (source or "").strip().lower()
    key = (subject_key or "").strip()
    if not src or not key:
        return False

    if src == "scholar":
        return key.startswith("id:")
    if src == "github":
        return key.startswith("login:")
    if src == "linkedin":
        return key.startswith("url:")

    return True
