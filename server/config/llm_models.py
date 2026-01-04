"""
LLM model selection helpers.

This project uses OpenRouter as the primary LLM gateway. We keep model selection
in env vars so deployments can switch providers/models without code changes.

Priority (highest -> lowest):
1) Caller passes `model=...` explicitly
2) Per-task override: `DINQ_LLM_TASK_MODEL_<TASK_KEY>`
3) Profile default: `DINQ_LLM_MODEL_<PROFILE>` (or `OPENROUTER_MODEL_<PROFILE>`)
4) Legacy global: `OPENROUTER_MODEL`
5) Built-in defaults (speed-first)
"""

from __future__ import annotations

import os
import re
from typing import Optional

from server.config.env_loader import load_environment_variables


# Best effort: make sure .env.* is loaded for scripts importing this module.
load_environment_variables(log_dinq_vars=False)


def _task_key(task: str) -> str:
    raw = str(task or "").strip()
    if not raw:
        return ""
    return re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").upper()


def task_override_env(task: str) -> str:
    """
    Env var name used to override a single task's model.

    Example:
      task="github_ai" -> DINQ_LLM_TASK_MODEL_GITHUB_AI
      task="juris.salary_eval" -> DINQ_LLM_TASK_MODEL_JURIS_SALARY_EVAL
    """

    return f"DINQ_LLM_TASK_MODEL_{_task_key(task)}"


def resolve_task_model(task: Optional[str]) -> str:
    if not task:
        return ""
    key = task_override_env(task)
    return (os.getenv(key) or "").strip()


def _first_set(*values: Optional[str]) -> str:
    for v in values:
        if v and str(v).strip():
            return str(v).strip()
    return ""


# Built-in defaults (speed-first).
#
# These are *route specs* understood by the LLM gateway and may be comma-separated multi-routes.
# Format examples:
#   - OpenRouter only: "google/gemini-2.5-flash"
#   - Groq primary + OpenRouter fallback: "groq:llama-3.1-8b-instant,google/gemini-2.5-flash-lite"
DEFAULT_FAST = "groq:llama-3.1-8b-instant,google/gemini-2.5-flash-lite"
DEFAULT_BALANCED = "groq:llama-3.1-8b-instant,google/gemini-2.5-flash"
DEFAULT_FLASH_PREVIEW = "groq:llama-3.1-8b-instant,google/gemini-3-flash-preview"
DEFAULT_CODE_FAST = "groq:llama-3.1-8b-instant,x-ai/grok-code-fast-1"
DEFAULT_REASONING_FAST = "groq:llama-3.1-8b-instant,x-ai/grok-4.1-fast"

# Built-in per-task overrides (bench-backed). These are route specs and may include provider prefixes:
#   - OpenRouter: "google/gemini-2.5-flash"
#   - Groq:       "groq:llama-3.1-8b-instant"
#
# NOTE: Env vars still win over these defaults.
_BUILTIN_TASK_MODEL_OVERRIDES = {
    # Strict JSON bundles: Groq first; OpenRouter fallback for robustness.
    "github_enrich_bundle": "groq:llama-3.1-8b-instant,google/gemini-2.5-flash",
    "scholar_level_fast": "groq:llama-3.1-8b-instant,google/gemini-2.5-flash",
    "linkedin_enrich_bundle": "groq:llama-3.1-8b-instant,google/gemini-2.5-flash",
    "github_best_pr": "groq:llama-3.1-8b-instant,google/gemini-2.5-flash",
    # Text tasks: still Groq primary; Flash-Lite as low-latency fallback.
    "linkedin_roast": "groq:llama-3.1-8b-instant,google/gemini-2.5-flash-lite",
    "researcher_evaluation": "groq:llama-3.1-8b-instant,google/gemini-2.5-flash-lite",
}


_DEFAULT_GROQ_ROUTE = "groq:llama-3.1-8b-instant"
_DEFAULT_OPENROUTER_FALLBACK = "google/gemini-2.5-flash-lite"


def _ensure_groq_primary(route_spec: str) -> str:
    parts = [p.strip() for p in str(route_spec or "").split(",") if str(p).strip()]
    groq: Optional[str] = None
    rest: list[str] = []
    seen: set[str] = set()

    for p in parts:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        if key.startswith("groq:") and groq is None:
            groq = p
        else:
            rest.append(p)

    if groq is None:
        groq = _DEFAULT_GROQ_ROUTE

    # Ensure Groq route is first (de-duped).
    out = [groq] + [p for p in rest if p.lower() != groq.lower()]
    if len(out) == 1:
        out.append(_DEFAULT_OPENROUTER_FALLBACK)
    return ",".join(out)


def get_model(profile: str = "fast", *, task: Optional[str] = None) -> str:
    """
    Return OpenRouter model ID for the given profile/task.

    Profiles:
      - fast: speed-first (default)
      - balanced: better quality while still fast
      - flash_preview: preview flash model
      - code_fast: fast model tuned for code reasoning
      - reasoning_fast: fast reasoning model
    """

    task_override = resolve_task_model(task)
    if task_override:
        return _ensure_groq_primary(task_override)
    if task:
        built_in = _BUILTIN_TASK_MODEL_OVERRIDES.get(str(task))
        if built_in and str(built_in).strip():
            return _ensure_groq_primary(str(built_in).strip())

    p = (profile or "fast").strip().lower()

    if p in ("balanced", "quality"):
        return _ensure_groq_primary(
            _first_set(
            os.getenv("DINQ_LLM_MODEL_BALANCED"),
            os.getenv("OPENROUTER_MODEL_BALANCED"),
            os.getenv("OPENROUTER_MODEL"),
            DEFAULT_BALANCED,
            )
        )

    if p in ("flash_preview", "preview"):
        return _ensure_groq_primary(
            _first_set(
            os.getenv("DINQ_LLM_MODEL_FLASH_PREVIEW"),
            os.getenv("OPENROUTER_MODEL_FLASH_PREVIEW"),
            os.getenv("OPENROUTER_MODEL"),
            DEFAULT_FLASH_PREVIEW,
            )
        )

    if p in ("code_fast", "code"):
        return _ensure_groq_primary(
            _first_set(
            os.getenv("DINQ_LLM_MODEL_CODE_FAST"),
            os.getenv("OPENROUTER_MODEL_CODE_FAST"),
            os.getenv("OPENROUTER_MODEL"),
            DEFAULT_CODE_FAST,
            )
        )

    if p in ("reasoning_fast", "reasoning"):
        return _ensure_groq_primary(
            _first_set(
            os.getenv("DINQ_LLM_MODEL_REASONING_FAST"),
            os.getenv("OPENROUTER_MODEL_REASONING_FAST"),
            os.getenv("OPENROUTER_MODEL"),
            DEFAULT_REASONING_FAST,
            )
        )

    # fast (default)
    return _ensure_groq_primary(
        _first_set(
        os.getenv("DINQ_LLM_MODEL_FAST"),
        os.getenv("OPENROUTER_MODEL_FAST"),
        os.getenv("OPENROUTER_MODEL"),
        DEFAULT_FAST,
        )
    )


def get_default_model() -> str:
    # Default for callers that don't specify a profile.
    return get_model("fast")
