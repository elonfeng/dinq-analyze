"""
Scholar PK Handler API

This module handles streaming API requests and responses for scholar PK.
"""

import logging
from typing import Any, Dict, Generator, Optional

# 导入模块化的Scholar PK API组件
from server.api.scholar_pk.pk_processor import build_scholar_pk_task_fn
from server.utils.stream_protocol import create_error_event, create_event
from server.utils.stream_task import run_streaming_task

# 设置日志记录器
logger = logging.getLogger(__name__)

# 存储活跃会话
active_pk_sessions: Dict[str, Dict[str, Any]] = {}

def build_pk_task_fn(
    query1: str,
    query2: str,
    *,
    user_id: Optional[str] = None,
    trace_id: Optional[str] = None,
):
    return build_scholar_pk_task_fn(
        query1=query1,
        query2=query2,
        active_sessions=active_pk_sessions,
        user_id=user_id,
        trace_id=trace_id,
    )

def stream_pk_thinking_process(query1: str, query2: str, user_id: Optional[str] = None) -> Generator[str, None, None]:
    """Generate a streaming response for scholar PK process

    Args:
        query1: First researcher query
        query2: Second researcher query
        user_id: ID of the user making the request (for tracking API usage)

    Yields:
        Formatted stream messages
    """
    try:
        task_fn = build_pk_task_fn(query1, query2, user_id=user_id, trace_id=None)

        def result_event_builder(result_type: str, payload: Any):
            if result_type == "success":
                return None
            message = str(payload)
            lowered = message.lower()
            code = "internal_error"
            retryable = False
            if "cancel" in lowered:
                code = "cancelled"
                retryable = True
            return create_error_event(
                source="scholar",
                code=code,
                message=message,
                retryable=retryable,
                detail={"researcher1": query1, "researcher2": query2},
                step="pk_error",
            )

        yield from run_streaming_task(
            source="scholar",
            task_fn=task_fn,
            timeout_seconds=300,
            keepalive_seconds=15,
            result_event_builder=result_event_builder,
        )
    except Exception as e:
        logger.error(f"Error in stream_pk_thinking_process: {str(e)}")
        # 返回错误消息
        from server.utils.stream_protocol import create_final_content, format_stream_message
        yield format_stream_message(create_final_content(f"An error occurred: {str(e)}"))
