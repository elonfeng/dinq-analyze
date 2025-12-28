#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Dict, Iterable, Tuple


def _mask(name: str, value: str) -> str:
    if not value:
        return ""
    upper = name.upper()
    if any(k in upper for k in ("KEY", "TOKEN", "SECRET", "PASSWORD", "DSN")):
        return "***"
    if len(value) <= 6:
        return value
    return f"{value[:2]}***{value[-2:]}"


def _as_bool(name: str) -> bool:
    return (os.getenv(name, "") or "").strip().lower() in ("1", "true", "yes", "on")


def _gather() -> Dict[str, str]:
    from server.config.env_loader import load_environment_variables
    from server.config.api_keys import API_KEYS

    load_environment_variables(log_dinq_vars=False)

    out: Dict[str, str] = {}
    out.update(API_KEYS)

    # Also capture a few non-API_KEYS envs that affect runtime/tests.
    for k in (
        "DINQ_ENV",
        "DINQ_API_DOMAIN",
        "DINQ_DB_URL",
        "DINQ_AUTH_BYPASS",
        "DINQ_EMAIL_BACKEND",
        "DINQ_SCHOLAR_FETCH_MAX_INFLIGHT_PER_DOMAIN",
        "DINQ_SCHOLAR_FETCH_DISK_CACHE_DIR",
    ):
        out[k] = os.getenv(k, "") or ""
    return out


def main() -> None:
    keys = _gather()

    # Order is opinionated: common -> optional.
    order: Tuple[str, ...] = (
        "DINQ_ENV",
        "DINQ_API_DOMAIN",
        "DINQ_DB_URL",
        "DINQ_AUTH_BYPASS",
        "DINQ_EMAIL_BACKEND",
        "GITHUB_TOKEN",
        "CRAWLBASE_API_TOKEN",
        "FIRECRAWL_API_KEY",
        "OPENROUTER_API_KEY",
        "GENERIC_OPENROUTER_API_KEY",
        "KIMI_API_KEY",
        "TAVILY_API_KEY",
        "YOUTUBE_API_KEY",
        "SCRAPINGDOG_API_KEY",
        "APIFY_API_KEY",
        "RESEND_API_KEY",
        "AXIOM_ENABLED",
        "AXIOM_TOKEN",
        "SENTRY_DSN",
        "DINQ_SCHOLAR_FETCH_MAX_INFLIGHT_PER_DOMAIN",
        "DINQ_SCHOLAR_FETCH_DISK_CACHE_DIR",
    )

    print("DINQ key status (masked):")
    for name in order:
        value = keys.get(name, "") or os.getenv(name, "") or ""
        present = "Y" if bool(value) else "N"
        masked = _mask(name, value)
        print(f"- {name} = {present} {masked}".rstrip())

    print("")
    print("Smoke switches:")
    print(f"- DINQ_RUN_ONLINE_SMOKE = {_as_bool('DINQ_RUN_ONLINE_SMOKE')}")
    print(f"- DINQ_SMOKE_SCHOLAR   = {_as_bool('DINQ_SMOKE_SCHOLAR')}")


if __name__ == "__main__":
    main()
