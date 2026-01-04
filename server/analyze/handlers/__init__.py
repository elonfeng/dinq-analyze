"""
Card handlers for the analysis pipeline.

This module provides a cleaner abstraction for card execution,
separating concerns and making the codebase more maintainable.
"""
from __future__ import annotations

__all__ = [
    "CardHandler",
    "CardResult",
    "ExecutionContext",
    "HandlerRegistry",
]
