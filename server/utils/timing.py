from __future__ import annotations

import time
from typing import Callable, Optional, TypeVar


def now_perf() -> float:
    return time.perf_counter()


def elapsed_ms(start: float, *, end: Optional[float] = None) -> int:
    if end is None:
        end = time.perf_counter()
    return max(0, int((float(end) - float(start)) * 1000))


T = TypeVar("T")


def time_call(fn: Callable[[], T]) -> tuple[T, int]:
    start = time.perf_counter()
    out = fn()
    return out, elapsed_ms(start)

