"""
Scholar API Utilities

This module contains utility functions for scholar API.
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Any

from server.utils.stream_protocol import create_think_content, create_event

# 设置日志记录器
logger = logging.getLogger(__name__)

def format_event_message(event_type: str, data: Dict[str, Any]) -> str:
    """格式化特定事件类型的消息

    Args:
        event_type: 事件类型
        data: 事件数据

    Returns:
        格式化的事件消息
    """
    # 统一 SSE 协议：只输出 data 行，事件类型放在 JSON 中
    payload: Dict[str, Any] = dict(data or {})
    payload.setdefault("source", "scholar")
    payload.setdefault("event_type", event_type)
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

def create_state_message(content: str, state: str = "thinking", progress: float = None) -> Dict[str, Any]:
    """创建带有状态信息、时间戳和可选进度信息的消息

    Args:
        content: 消息内容
        state: 消息状态，默认为"thinking"
        progress: 可选的进度值（0-100），表示分析完成百分比

    Returns:
        带有状态信息、时间戳和可选进度信息的消息字典
    """
    # 获取当前时间戳
    current_time = time.time()
    formatted_time = datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')

    # 在消息内容前添加时间戳
    timestamped_content = f"{content} "

    base = create_think_content(timestamped_content)
    base["state"] = state
    base["timestamp"] = formatted_time

    unified = create_event(
        source="scholar",
        event_type="progress",
        message=timestamped_content,
        step=state,
        progress=progress,
        legacy_type=base.get("type"),
    )

    # 合并 legacy 字段（content/state/timestamp/progress）到统一事件中，保证兼容
    unified.update(base)

    if progress is not None:
        unified["progress"] = progress

    return unified

def create_report_data_message(report_urls: Dict[str, str]) -> Dict[str, Any]:
    """创建报告数据消息

    Args:
        report_urls: 包含 JSON URL、HTML URL、研究者名称和可选的学者ID的字典

    Returns:
        报告数据消息字典
    """
    content = {
        "jsonUrl": report_urls["json_url"],
        "htmlUrl": report_urls["html_url"],
        "researcherName": report_urls["researcher_name"]
    }

    # 如果有学者ID，添加到内容中
    if "scholar_id" in report_urls:
        content["scholarId"] = report_urls["scholar_id"]

    if "completeness" in report_urls:
        content["completeness"] = report_urls["completeness"]

    event = create_event(
        source="scholar",
        event_type="data",
        message="Scholar report generated",
        payload=content,
        legacy_type="reportData",
    )
    # 为兼容旧前端，保留 content 字段
    event["content"] = content
    return event

def validate_scholar_query(query: str) -> bool:
    """验证查询是否与学者相关

    Args:
        query: 用户查询

    Returns:
        如果查询与学者相关则返回True，否则返回False
    """
    # 目前假设所有查询都是关于学者的
    logger.debug(f"Validating scholar query: {query}")
    return True
