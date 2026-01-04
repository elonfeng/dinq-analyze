"""
Utility functions for attaching _meta to card outputs.

This ensures consistent metadata across all sources and prevents
prune_empty from deleting valid but empty fields.
"""
from __future__ import annotations
from typing import Any, Dict, Optional


def ensure_meta(payload: Any, **kwargs: Any) -> Any:
    """
    Attach or update _meta in a dict payload.
    
    Args:
        payload: The card output (dict or other type)
        **kwargs: Meta fields to set/update
        
    Common kwargs:
        - preserve_empty: bool (default True) - prevent prune_empty from deleting empty fields
        - fallback: bool - mark as fallback payload
        - code: str - error/fallback code
        - source: str - which system generated this
        
    Returns:
        Modified payload with _meta attached
    """
    if not isinstance(payload, dict):
        # Can't attach meta to non-dict types
        return payload
    
    result = dict(payload)
    existing_meta = result.get("_meta")
    
    if not isinstance(existing_meta, dict):
        existing_meta = {}
    
    # Default: always preserve empty unless explicitly set to False
    if "preserve_empty" not in kwargs:
        kwargs["preserve_empty"] = True
    
    # Merge kwargs into existing meta
    meta = dict(existing_meta)
    meta.update(kwargs)
    
    result["_meta"] = meta
    return result


def extract_meta(payload: Any) -> Dict[str, Any]:
    """Extract _meta dict from payload, or return empty dict."""
    if isinstance(payload, dict):
        meta = payload.get("_meta")
        if isinstance(meta, dict):
            return dict(meta)
    return {}


def is_fallback(payload: Any) -> bool:
    """Check if payload is marked as fallback."""
    meta = extract_meta(payload)
    return bool(meta.get("fallback"))


def should_preserve_empty(payload: Any) -> bool:
    """Check if payload should skip prune_empty."""
    meta = extract_meta(payload)
    return bool(meta.get("preserve_empty"))
