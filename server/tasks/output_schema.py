"""Helpers for the unified job_cards.output schema.

Schema (stored in job_cards.output):
{
  "data": <any JSON>,   # final semantic payload for the card
  "stream": {           # accumulated incremental text for snapshot/UX
    "<field>": {
      "format": "markdown" | "text" | ...,
      "sections": {
        "<section>": "<text>"
      }
    }
  }
}
"""

from __future__ import annotations

from typing import Any, Dict, Tuple


def _coerce_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_output_envelope(value: Any) -> Dict[str, Any]:
    """
    Normalize legacy card output into the {data, stream} envelope.

    Rules:
    - If value looks like the envelope => keep.
    - If value is any other dict => treat as legacy "data".
    """

    if isinstance(value, dict) and ("data" in value or "stream" in value):
        data = value.get("data")
        stream = _coerce_dict(value.get("stream"))
        return {"data": data, "stream": stream}

    # Legacy: raw dict payload, string, None, etc.
    if isinstance(value, dict):
        return {"data": value, "stream": {}}
    return {"data": value, "stream": {}}


def extract_output_parts(value: Any) -> Tuple[Any, Dict[str, Any]]:
    env = ensure_output_envelope(value)
    return env.get("data"), _coerce_dict(env.get("stream"))
