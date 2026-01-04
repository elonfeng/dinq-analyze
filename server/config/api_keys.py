"""
Centralized API key registry.

安全约定：
- 本文件 **不提供任何真实密钥的默认值**。
- 真实密钥应通过环境变量或 `.env.local/.env.<env>.local`（gitignore）注入。
"""

from __future__ import annotations

import os
from typing import Dict, Iterable, Optional

from server.config.env_loader import load_environment_variables


# Best effort: make keys available for scripts that import API_KEYS directly.
load_environment_variables(log_dinq_vars=False)


_PRIMARY_KEYS: tuple[str, ...] = (
    # LLM
    "OPENROUTER_API_KEY",
    "GENERIC_OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "KIMI_API_KEY",
    "OPENROUTER_MODEL",
    # Crawling
    "CRAWLBASE_API_TOKEN",
    "FIRECRAWL_API_KEY",
    # Integrations
    "GITHUB_TOKEN",
    "TAVILY_API_KEY",
    "YOUTUBE_API_KEY",
    "SCRAPINGDOG_API_KEY",
    "APIFY_API_KEY",
    # Email
    "RESEND_API_KEY",
)


_ALIASES: Dict[str, Iterable[str]] = {
    # Legacy names kept for backward compatibility.
    "CRAWLBASE_API_TOKEN": ("CRAWLBASE_TOKEN",),
    "OPENROUTER_API_KEY": ("OPENROUTER_KEY",),
    "GROQ_API_KEY": ("GROQ_KEY", "DINQ_GROQ_API_KEY"),
}


def _lookup(name: str) -> str:
    value = os.getenv(name) or ""
    if value:
        return value
    for alias in _ALIASES.get(name, ()):
        value = os.getenv(alias) or ""
        if value:
            return value
    return ""


def load_api_keys() -> Dict[str, str]:
    keys: Dict[str, str] = {}
    for name in _PRIMARY_KEYS:
        keys[name] = _lookup(name)
    return keys


API_KEYS: Dict[str, str] = load_api_keys()


def get_api_key(name: str, default: str = "") -> str:
    value = API_KEYS.get(name)
    if value:
        return value
    return _lookup(name) or default


def get_openrouter_api_key() -> str:
    return get_api_key("OPENROUTER_API_KEY") or get_api_key("GENERIC_OPENROUTER_API_KEY")


def get_groq_api_key() -> str:
    return get_api_key("GROQ_API_KEY")


def get_openrouter_model(default: str = "") -> str:
    return get_api_key("OPENROUTER_MODEL", default=default)


def require_api_key(name: str) -> str:
    value = get_api_key(name)
    if not value:
        raise RuntimeError(f"Missing required API key: {name}")
    return value
