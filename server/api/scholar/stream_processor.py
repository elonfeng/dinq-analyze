"""
Scholar Stream Processor

统一 Scholar 流式分析管线：通过 build_stream_task_fn + run_streaming_task 统一样板与协议。
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from account.filter_scholar import filter_user_input
from server.api.scholar.report_generator import save_scholar_report
from server.api.scholar.utils import create_report_data_message, create_state_message
from server.config.api_keys import API_KEYS
from server.services.scholar.completeness import compute_scholar_completeness
from server.services.scholar.scholar_service import run_scholar_analysis
from server.utils.ai_tools import generate_session_id
from server.utils.api_usage_tracker import track_stream_completion
from server.utils.stream_protocol import create_status
from server.utils.streaming_task_builder import build_stream_task_fn

# Set up logger（支持trace ID）
try:
    from server.utils.trace_context import get_trace_logger

    logger = get_trace_logger(__name__)
except ImportError:
    # Fallback to regular logger if trace context is not available
    logger = logging.getLogger(__name__)


def handle_data_analysis_and_visualization(
    scholar_data: Dict[str, Any],
    thinking_logs: List[str],
    report_urls: Dict[str, str],
    progress_cb: Callable[[Dict[str, Any]], None],
) -> None:
    """
    Handle data analysis and visualization.

    Currently this emits a single high-level progress event. The detailed
    visualization steps can be expanded here in the future.
    """

    progress_cb(
        create_state_message(
            "Generating final analysis report...",
            progress=99.0,
        )
    )


def build_scholar_task_fn(
    query: str,
    active_sessions: Dict[str, Dict[str, Any]],
    user_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Callable[[Callable[[Dict[str, Any]], None], "queue.Queue"], None]:
    """
    构建给 run_streaming_task 使用的 task_fn(progress_cb, result_queue, cancel_event)。

    Scholar 侧仍保留 legacy 字段兼容（如 thinkContent/reportData 的 content），
    但任务样板（trace/异常/结果写入）统一走 build_stream_task_fn。
    """

    processed_input, is_name = filter_user_input(query)
    initial_scholar_id = None if is_name else processed_input

    def work(ctx, _limit_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        last_progress: float = 0.0

        def emit_state(message: str, *, progress: Optional[float] = None, state: str = "thinking") -> None:
            nonlocal last_progress
            if progress is not None:
                try:
                    progress_f = float(progress)
                except (TypeError, ValueError):
                    progress_f = last_progress
                progress_f = max(0.0, min(100.0, progress_f))
                # 保证进度单调不回退
                progress_f = max(last_progress, progress_f)
                last_progress = progress_f
                ctx.emit_raw(create_state_message(message, state=state, progress=progress_f))
                return
            ctx.emit_raw(create_state_message(message, state=state))

        if initial_scholar_id:
            emit_state(f"Detected Google Scholar ID: {initial_scholar_id}", progress=2.0)

        ctx.emit_raw(create_status("Processing query request..."))
        emit_state(f"Analyzing researcher: {query}", progress=4.0)
        emit_state("Preparing to retrieve scholar data...", progress=4.5)

        if ctx.cancelled():
            raise ValueError("Canceled")

        scholar_data = None

        api_token = API_KEYS.get("CRAWLBASE_API_TOKEN")

        def status_callback(msg: Any) -> None:
            # 注意：status_reporter.send_status 会吞异常，这里不要通过 raise 来“取消”
            if ctx.cancelled():
                return
            if isinstance(msg, dict):
                msg_text = msg.get("message", "")
                raw_progress = msg.get("progress")
            else:
                msg_text = str(msg)
                raw_progress = None

            # Scholar service 内部进度是 0-100，这里映射到 0-90，避免后续 reportData 阶段“进度回退”
            mapped_progress: Optional[float] = None
            if raw_progress is not None:
                try:
                    mapped_progress = float(raw_progress) * 0.9
                except (TypeError, ValueError):
                    mapped_progress = None

            emit_state(str(msg_text), progress=mapped_progress)

        if scholar_data is None:
            scholar_data = run_scholar_analysis(
                researcher_name=query if is_name else None,
                scholar_id=initial_scholar_id,
                use_crawlbase=True,
                api_token=api_token,
                callback=status_callback,
                use_cache=True,
                cache_max_age_days=3,
                cancel_event=ctx.cancel_event,
                user_id=user_id,
            )

        if ctx.cancelled():
            raise ValueError("Canceled")

        if not scholar_data:
            raise ValueError(
                f"Unable to retrieve scholar data for '{query}'. "
                "Please ensure you've entered the correct scholar name or ID."
            )

        emit_state("Academic data retrieval complete ✓", progress=90.0)

        extracted_scholar_id: Optional[str] = None
        researcher = scholar_data.get("researcher")
        if isinstance(researcher, dict):
            extracted_scholar_id = researcher.get("scholar_id")
        if not extracted_scholar_id:
            extracted_scholar_id = initial_scholar_id

        session_id = generate_session_id()
        active_sessions[session_id] = {
            "query": query,
            "status": "active",
            "report": scholar_data,
        }
        report_urls = save_scholar_report(scholar_data, query, session_id)
        if extracted_scholar_id:
            report_urls["scholar_id"] = extracted_scholar_id

        # Stable completeness for frontend rendering
        report_urls["completeness"] = compute_scholar_completeness(scholar_data)

        emit_state("Scholar report generated", progress=95.0)
        ctx.emit_raw(create_report_data_message(report_urls))

        handle_data_analysis_and_visualization(
            scholar_data,
            [],
            report_urls,
            lambda e: ctx.emit_raw(e),
        )

        report_data: Dict[str, Any] = {
            "jsonUrl": report_urls["json_url"],
            "htmlUrl": report_urls["html_url"],
            "researcherName": report_urls["researcher_name"],
        }
        if extracted_scholar_id:
            report_data["scholarId"] = extracted_scholar_id
        report_data["completeness"] = report_urls.get("completeness")

        return report_data

    def on_success(payload: Dict[str, Any]) -> None:
        if not user_id:
            return
        try:
            track_stream_completion(
                endpoint="/api/stream",
                query=query,
                scholar_id=payload.get("scholarId"),
                status="success",
                user_id=user_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error tracking stream completion: %s", exc)

    def on_error(error_message: str) -> None:
        if not user_id:
            return
        try:
            track_stream_completion(
                endpoint="/api/stream",
                query=query,
                scholar_id=initial_scholar_id,
                status="error",
                error_message=error_message,
                user_id=user_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error tracking stream completion: %s", exc)

    return build_stream_task_fn(
        source="scholar",
        trace_id=trace_id,
        usage_limiter=None,
        usage_config=None,
        user_id=user_id,
        start_message=f"Starting Scholar analysis: {query}",
        start_payload={"query": query},
        work=work,
        on_success=on_success,
        on_error=on_error,
    )
