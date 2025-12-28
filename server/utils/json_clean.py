from __future__ import annotations

from typing import Any


def prune_empty(value: Any) -> Any:
    """
    Recursively remove empty values from JSON-like payloads.

    Empty is defined as:
    - None
    - empty/whitespace-only strings
    - empty dicts / lists (after pruning)

    Notes:
    - Numbers (including 0) and booleans are preserved.
    - For lists, empty items are removed; if the list becomes empty, it is removed by the parent.
    - For dicts, keys whose values become empty are removed; if the dict becomes empty, it is removed by the parent.
    """

    if value is None:
        return None

    if isinstance(value, str):
        s = value.strip()
        return s or None

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            ks = str(k).strip()
            if not ks:
                continue
            pv = prune_empty(v)
            if pv is None:
                continue
            # Drop empty containers that remain after pruning.
            if isinstance(pv, (dict, list)) and not pv:
                continue
            out[ks] = pv
        return out or None

    if isinstance(value, list):
        out: list[Any] = []
        for item in value:
            pv = prune_empty(item)
            if pv is None:
                continue
            if isinstance(pv, (dict, list)) and not pv:
                continue
            out.append(pv)
        return out or None

    return value
