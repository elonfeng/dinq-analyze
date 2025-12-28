"""
Streaming task builder helpers.

目标：把 streaming API 的重复样板（trace/usage/cancel/cache/error/progress）集中在一处，
让各业务端点只关心“怎么分析”和“怎么组装结果”。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from server.utils.stream_protocol import create_event


ProgressCb = Callable[[Dict[str, Any]], None]
ResultQueue = Any


@dataclass(frozen=True)
class UsageLimitConfig:
    endpoints: Sequence[str]
    limit: int = 5
    days: int = 30


class StreamingTaskContext:
    def __init__(self, *, source: str, progress_cb: ProgressCb, cancel_event: Optional[Any] = None):
        self.source = source
        self._progress_cb = progress_cb
        self._cancel_event = cancel_event

    @property
    def cancel_event(self) -> Optional[Any]:
        return self._cancel_event

    def cancelled(self) -> bool:
        return bool(self._cancel_event) and getattr(self._cancel_event, "is_set", lambda: False)()

    def emit_raw(self, event: Any) -> None:
        """
        Emit a pre-built event payload directly to the streaming channel.

        Useful for legacy helpers that already construct a dict with extra
        compatibility fields (e.g. `content`), while still respecting
        cancellation.
        """

        if self.cancelled():
            return
        if isinstance(event, dict) and "source" not in event:
            event["source"] = self.source
        self._progress_cb(event)

    def emit(
        self,
        *,
        event_type: str,
        message: str,
        step: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        legacy_type: Optional[str] = None,
    ) -> None:
        if self.cancelled():
            return
        self._progress_cb(
            create_event(
                source=self.source,
                event_type=event_type,
                message=message,
                step=step,
                payload=payload,
                legacy_type=legacy_type,
            )
        )

    def start(self, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self.emit(event_type="start", message=message, payload=payload, legacy_type="start")

    def progress(self, step: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self.emit(event_type="progress", step=step, message=message, payload=payload, legacy_type="progress")


def build_stream_task_fn(
    *,
    source: str,
    trace_id: Optional[str],
    usage_limiter: Optional[Any],
    usage_config: Optional[UsageLimitConfig],
    user_id: Optional[str],
    start_message: str,
    start_payload: Optional[Dict[str, Any]] = None,
    cache_lookup: Optional[Callable[[StreamingTaskContext], Optional[Any]]] = None,
    cache_hit_payload_builder: Optional[Callable[[Any, Dict[str, Any]], Dict[str, Any]]] = None,
    work: Callable[[StreamingTaskContext, Optional[Dict[str, Any]]], Dict[str, Any]] = None,
    on_success: Optional[Callable[[Dict[str, Any]], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
) -> Callable[[ProgressCb, ResultQueue, Optional[Any]], None]:
    """
    构建一个可给 run_streaming_task 使用的 task_fn(progress_cb, result_queue, cancel_event)。

    - 统一 trace 传播（如果提供 trace_id）
    - 统一 usage limit（如果提供 usage_config + usage_limiter）
    - 统一缓存命中逻辑（如果提供 cache_lookup）
    - 统一异常捕获与 result_queue 写入
    """

    if work is None:
        raise ValueError("work is required")

    def task_fn(progress_cb: ProgressCb, result_queue: ResultQueue, cancel_event: Optional[Any] = None) -> None:
        if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
            return

        if trace_id:
            try:
                from server.utils.trace_context import TraceContext as _TraceContext

                _TraceContext.set_trace_id(trace_id)
            except Exception:  # noqa: BLE001
                pass

        ctx = StreamingTaskContext(source=source, progress_cb=progress_cb, cancel_event=cancel_event)
        ctx.start(start_message, payload=start_payload)

        limit_info: Optional[Dict[str, Any]] = None
        if usage_limiter is not None and usage_config is not None:
            ctx.progress("usage_check", "Checking usage limits...")
            is_allowed, limit_info = usage_limiter.check_monthly_limit(
                user_id=user_id,
                endpoints=list(usage_config.endpoints),
                limit=usage_config.limit,
                days=usage_config.days,
            )
            if not is_allowed:
                if on_error is not None:
                    on_error("Monthly usage limit exceeded")
                result_queue.put(("error", "Monthly usage limit exceeded"))
                return

        if cache_lookup is not None:
            ctx.progress("check_cache", "Checking cache...")
            cached = cache_lookup(ctx)
            if cached is not None:
                ctx.progress("cache_found", "Found cached result")
                payload = (
                    cache_hit_payload_builder(cached, limit_info or {})
                    if cache_hit_payload_builder is not None
                    else {"data": cached, "from_cache": True, "usage_info": limit_info or {}}
                )
                if on_success is not None:
                    on_success(payload)
                result_queue.put(("success", payload))
                return

        if ctx.cancelled():
            if on_error is not None:
                on_error("Canceled")
            result_queue.put(("error", "Canceled"))
            return

        try:
            payload = work(ctx, limit_info)
            if on_success is not None:
                on_success(payload)
            result_queue.put(("success", payload))
        except Exception as exc:  # noqa: BLE001
            if on_error is not None:
                on_error(str(exc))
            result_queue.put(("error", str(exc)))

    return task_fn
