"""
Generic helpers for running long-running analysis tasks with Server-Sent Events.

This module centralizes the common pattern used by multiple streaming APIs:
start a background task, collect progress updates, and stream them to the
client using a unified event schema.
"""

import threading
import queue
import time
import inspect
from typing import Any, Callable, Dict, Generator, Optional, Tuple, Union

from server.utils.stream_protocol import (
    create_error_event,
    create_event,
    format_stream_message,
)


ProgressEvent = Union[Dict[str, Any], str]
ResultType = Tuple[str, Any]  # ("success" | "error", payload_or_message)

CancelEvent = threading.Event


def _task_accepts_cancel_event(task_fn: Callable[..., Any]) -> bool:
    try:
        sig = inspect.signature(task_fn)
    except (TypeError, ValueError):
        return False

    positional = [
        p
        for p in sig.parameters.values()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    if len(positional) >= 3:
        return True
    return any(p.kind == p.VAR_POSITIONAL for p in sig.parameters.values())


def run_streaming_task(
    *,
    source: str,
    task_fn: Callable[[Callable[[ProgressEvent], None], queue.Queue], None],
    timeout_seconds: int = 300,
    keepalive_seconds: Optional[float] = None,
    result_event_builder: Optional[Callable[[str, Any], Optional[Dict[str, Any]]]] = None,
    progress_queue_maxsize: int = 1000,
) -> Generator[str, None, None]:
    """
    Run a long-lived analysis task and yield SSE messages.

    Args:
        source: Logical source of the events ("scholar" | "github" | "linkedin").
        task_fn: A callable that accepts (progress_callback, result_queue) and
                 performs the actual analysis work. It must put exactly one
                 ResultType tuple into result_queue before returning.
                 Optionally, it can accept a third argument (cancel_event) to
                 support cooperative cancellation on timeout/client disconnect.
        timeout_seconds: Maximum wall-clock time before aborting with timeout.
        keepalive_seconds: If set, emit periodic "ping" events when no progress
                           events are sent, to keep the SSE connection alive.

    Yields:
        SSE-formatted strings.
    """

    progress_queue: "queue.Queue[ProgressEvent]" = queue.Queue(maxsize=progress_queue_maxsize)
    result_queue: "queue.Queue[ResultType]" = queue.Queue(maxsize=1)
    cancel_event: CancelEvent = threading.Event()

    def progress_callback(event: ProgressEvent) -> None:
        """
        Enqueue a progress event emitted by the task function.

        The event is expected to already follow the unified schema at the
        dictionary level (source, event_type, message, etc.). The helper will
        ensure the source is set if missing.
        """

        if cancel_event.is_set():
            return

        if isinstance(event, dict) and "source" not in event:
            event["source"] = source
        try:
            progress_queue.put_nowait(event)
        except queue.Full:
            # In case of heavy spam, drop oldest silently rather than blocking.
            try:
                _ = progress_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                progress_queue.put_nowait(event)
            except queue.Full:
                # If still full, drop this event.
                return

    def task_wrapper() -> None:
        try:
            if _task_accepts_cancel_event(task_fn):
                task_fn(progress_callback, result_queue, cancel_event)
            else:
                task_fn(progress_callback, result_queue)
        except Exception as exc:  # noqa: BLE001
            # On unexpected exception, report via result_queue if possible.
            try:
                result_queue.put_nowait(("error", str(exc)))
            except queue.Full:
                pass

    worker = threading.Thread(target=task_wrapper, daemon=True)
    worker.start()

    start_time = time.time()
    last_activity_at = time.monotonic()

    try:
        # Stream progress events while the worker is running or until timeout.
        while worker.is_alive():
            # Drain progress queue with small blocking timeout to avoid busy loop.
            try:
                event = progress_queue.get(timeout=0.5)
                if isinstance(event, str):
                    yield event
                else:
                    yield format_stream_message(event)
                last_activity_at = time.monotonic()
            except queue.Empty:
                pass

            if keepalive_seconds is not None and keepalive_seconds > 0:
                now = time.monotonic()
                if now - last_activity_at >= keepalive_seconds:
                    ping_event = create_event(
                        source=source,
                        event_type="ping",
                        message="",
                        step="keepalive",
                        legacy_type="ping",
                    )
                    ping_event.setdefault("content", "")
                    yield format_stream_message(ping_event)
                    last_activity_at = now

            if time.time() - start_time > timeout_seconds:
                cancel_event.set()

                # Emit timeout error and ask worker to finish; result may still
                # arrive, but client has already received an error.
                timeout_event = create_error_event(
                    source=source,
                    code="timeout",
                    message="Analysis timeout",
                    retryable=True,
                    detail={"timeout_seconds": timeout_seconds},
                    step="timeout",
                )
                yield format_stream_message(timeout_event)
                end_event = create_event(
                    source=source,
                    event_type="end",
                    message="Analysis stream closed (timeout)",
                )
                yield format_stream_message(end_event)

                # Give cooperative tasks a brief chance to stop.
                worker.join(timeout=0.2)
                return
    finally:
        # Best effort: ask worker to stop when client disconnects / generator closes.
        cancel_event.set()

    # Worker has finished; try to emit any remaining progress events quickly.
    while True:
        try:
            event = progress_queue.get_nowait()
            if isinstance(event, str):
                yield event
            else:
                yield format_stream_message(event)
        except queue.Empty:
            break

    # Emit the final result, if any.
    try:
        result_type, payload = result_queue.get_nowait()
    except queue.Empty:
        # No explicit result; send a generic end event.
        end_event = create_event(
            source=source,
            event_type="end",
            message="Analysis finished without explicit result",
        )
        yield format_stream_message(end_event)
        return

    event: Optional[Dict[str, Any]] = None
    if result_event_builder is not None:
        event = result_event_builder(result_type, payload)
    else:
        if result_type == "success":
            event = create_event(
                source=source,
                event_type="final",
                message="Analysis completed",
                payload=payload if isinstance(payload, dict) else {"result": payload},
            )
        else:
            code = "internal_error"
            message = str(payload)
            retryable = False
            detail: Optional[Dict[str, Any]] = None

            if isinstance(payload, dict):
                if isinstance(payload.get("code"), str) and isinstance(payload.get("message"), str):
                    code = payload.get("code") or code
                    message = payload.get("message") or message
                    retryable = bool(payload.get("retryable", False))
                    detail_value = payload.get("detail")
                    detail = detail_value if isinstance(detail_value, dict) else None
                else:
                    message = str(payload.get("message") or payload.get("error") or message)
                    detail = payload
            else:
                lowered = message.lower()
                if "limit" in lowered and "exceed" in lowered:
                    code = "usage_limit"
                if "cancel" in lowered:
                    code = "cancelled"
                    retryable = True

            event = create_error_event(
                source=source,
                code=code,
                message=message,
                retryable=retryable,
                detail=detail,
                step="error",
            )

    if event is not None:
        yield format_stream_message(event)

    end_event = create_event(
        source=source,
        event_type="end",
        message="Analysis stream closed",
    )
    yield format_stream_message(end_event)
