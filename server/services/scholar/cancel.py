"""
Scholar cancellation helpers.

Scholar 分析链路历史上是“尽量跑完”的风格，但在 SSE streaming 场景下，
需要支持客户端断开/超时后的协作取消，尽快停止后续网络请求与长循环。
"""

from __future__ import annotations

from typing import Any, Optional


class ScholarTaskCancelled(Exception):
    pass


def cancelled(cancel_event: Optional[Any]) -> bool:
    return bool(cancel_event) and getattr(cancel_event, "is_set", lambda: False)()


def raise_if_cancelled(cancel_event: Optional[Any]) -> None:
    if cancelled(cancel_event):
        raise ScholarTaskCancelled("Canceled")

