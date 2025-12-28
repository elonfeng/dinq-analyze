"""Thread-local LLM streaming context."""
from __future__ import annotations

from contextlib import contextmanager
import threading
from typing import Callable, Optional, Tuple


_stream_ctx = threading.local()


def set_llm_stream_context(
    callback: Optional[Callable[[str], None]],
    force_stream: bool = True,
) -> None:
    _stream_ctx.callback = callback
    _stream_ctx.force_stream = force_stream


def clear_llm_stream_context() -> None:
    _stream_ctx.callback = None
    _stream_ctx.force_stream = False


def get_llm_stream_context() -> Tuple[Optional[Callable[[str], None]], bool]:
    callback = getattr(_stream_ctx, "callback", None)
    force_stream = bool(getattr(_stream_ctx, "force_stream", False))
    return callback, force_stream


@contextmanager
def llm_stream_context(
    callback: Optional[Callable[[str], None]],
    force_stream: bool = True,
):
    prev_callback = getattr(_stream_ctx, "callback", None)
    prev_force = getattr(_stream_ctx, "force_stream", False)
    set_llm_stream_context(callback, force_stream)
    try:
        yield
    finally:
        if prev_callback is None:
            clear_llm_stream_context()
        else:
            _stream_ctx.callback = prev_callback
            _stream_ctx.force_stream = prev_force
