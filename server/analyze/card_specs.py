"""Card streaming specs (field/sections/format) for UI-friendly incremental output."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


# NOTE:
# - We only enable streaming for user-facing markdown/text fields.
# - For cards that return JSON objects, streaming partial JSON is poor UX; keep them non-streaming.
#
# Spec schema:
# {
#   "field": "critical_evaluation" | "roast" | ...,
#   "format": "markdown" | "text",
#   "sections": ["overview", "strengths", ...],  # fixed list for the card
#   "route": "fixed" | "marker",                 # marker => parse <!--section:...--> switches
# }
_STREAM_SPECS: Dict[Tuple[str, str], Dict[str, Any]] = {
    # Scholar: critical review is a single markdown/text stream.
    ("scholar", "criticalreview"): {"field": "evaluation", "format": "markdown", "sections": ["main"], "route": "fixed", "flush_chars": 60},
    # GitHub: roast is a single markdown/text stream.
    ("github", "roast"): {"field": "roast", "format": "markdown", "sections": ["main"], "route": "fixed"},
    # LinkedIn: roast/summary.about are single streams.
    ("linkedin", "roast"): {"field": "roast", "format": "markdown", "sections": ["main"], "route": "fixed"},
    ("linkedin", "summary"): {"field": "about", "format": "markdown", "sections": ["main"], "route": "fixed"},
}


def get_stream_spec(source: str, card_type: str) -> Optional[Dict[str, Any]]:
    key = (str(source or "").strip().lower(), str(card_type or "").strip().lower())
    spec = _STREAM_SPECS.get(key)
    if not spec:
        return None
    return dict(spec)


def marker_prefix() -> str:
    return "<!--section:"


def marker_suffix() -> str:
    return "-->"
